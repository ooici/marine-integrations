"""
@package mi.instrument.noaa.lily.ooicore.driver
@file marine-integrations/mi/instrument/noaa/botpt/lily/driver.py
@author David Everett
@brief Driver for the ooicore
Release notes: Driver for LILY TILT on the RSN-BOTPT instrument (v.6)
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import re
import time
import json

import ntplib

from mi.core.log import get_logger
from mi.core.common import BaseEnum
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType
from mi.instrument.noaa.botpt.driver import BotptDataParticleType
from mi.instrument.noaa.botpt.driver import BotptStatus01Particle
from mi.instrument.noaa.botpt.driver import BotptProtocolState
from mi.instrument.noaa.botpt.driver import BotptExportedInstrumentCommand
from mi.instrument.noaa.botpt.driver import BotptProtocolEvent
from mi.instrument.noaa.botpt.driver import BotptCapability
from mi.instrument.noaa.botpt.driver import BotptStatus02Particle
from mi.instrument.noaa.botpt.driver import NEWLINE
from mi.instrument.noaa.botpt.driver import BotptProtocol
from mi.instrument.noaa.botpt.driver import BotptStatus02ParticleKey
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentDataException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import SampleException


log = get_logger()

###
#    Driver Constant Definitions
###

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

DISCOVER_REGEX = re.compile(r'(LILY,.*%s)' % NEWLINE)


class ScheduledJob(BaseEnum):
    LEVELING_TIMEOUT = 'leveling_timeout'


class ProtocolState(BotptProtocolState):
    """
    Instrument protocol states
    """
    COMMAND_LEVELING = 'LILY_DRIVER_STATE_COMMAND_LEVELING'
    AUTOSAMPLE_LEVELING = 'LILY_DRIVER_STATE_AUTOSAMPLE_LEVELING'


class ExportedInstrumentCommand(BotptExportedInstrumentCommand):
    START_LEVELING = "EXPORTED_INSTRUMENT_START_LEVELING"
    STOP_LEVELING = "EXPORTED_INSTRUMENT_STOP_LEVELING"


class ProtocolEvent(BotptProtocolEvent):
    """
    Protocol events
    """
    START_LEVELING = ExportedInstrumentCommand.START_LEVELING
    STOP_LEVELING = ExportedInstrumentCommand.STOP_LEVELING
    LEVELING_TIMEOUT = "PROTOCOL_EVENT_LEVELING_TIMEOUT"


class Capability(BotptCapability):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    START_LEVELING = ProtocolEvent.START_LEVELING
    STOP_LEVELING = ProtocolEvent.STOP_LEVELING


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    AUTO_RELEVEL = "auto_relevel"  # Auto-relevel mode
    XTILT_TRIGGER = "xtilt_relevel_trigger"
    YTILT_TRIGGER = "ytilt_relevel_trigger"
    LEVELING_TIMEOUT = "relevel_timeout"
    LEVELING_FAILED = "leveling_failed"


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

class DataParticleType(BotptDataParticleType):
    LILY_PARSED = 'botpt_lily_sample'
    LILY_LEVELING = 'botpt_lily_leveling'
    LILY_STATUS_01 = 'botpt_lily_status_01'
    LILY_STATUS_02 = 'botpt_lily_status_02'


class LILYDataParticleKey(BaseEnum):
    SENSOR_ID = 'sensor_id'
    TIME = "date_time_string"
    X_TILT = "lily_x_tilt"
    Y_TILT = "lily_y_tilt"
    MAG_COMPASS = "compass_direction"
    TEMP = "lily_temp"
    SUPPLY_VOLTS = "supply_voltage"
    SN = "serial_number"
    OUT_OF_RANGE = 'lily_out_of_range'


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

    def __init__(self, raw_data, out_of_range=False,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP):

        super(LILYDataParticle, self).__init__(raw_data,
                                               port_timestamp,
                                               internal_timestamp,
                                               preferred_timestamp)
        self.out_of_range = out_of_range

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
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.SENSOR_ID,
             DataParticleKey.VALUE: 'LILY'},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.TIME,
             DataParticleKey.VALUE: lily_time},
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
             DataParticleKey.VALUE: sn},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.OUT_OF_RANGE,
             DataParticleKey.VALUE: self.out_of_range},
        ]

        return result


###############################################################################
# Status Particles
###############################################################################


class LILYStatus01Particle(BotptStatus01Particle):
    _data_particle_type = DataParticleType.LILY_STATUS_01


class LILYStatus02ParticleKey(BotptStatus02ParticleKey):
    USED_SAMPLES = 'lily_used_samples'
    TOTAL_SAMPLES = 'lily_total_samples'
    LOW_POWER_RATE = 'lily_low_power_data_rate'
    COMPASS_INSTALLED = 'lily_compass_installed'
    COMPASS_MAG_DECL = 'lily_compass_magnetic_declination'
    COMPASS_XOFFSET = 'lily_compass_x_offset'
    COMPASS_YOFFSET = 'lily_compass_y_offset'
    COMPASS_XRANGE = 'lily_compass_x_range'
    COMPASS_YRANGE = 'lily_compass_y_range'
    PID_IMAX = 'lily_pid_coeff_imax'
    PID_IMIN = 'lily_pid_coeff_imin'
    PID_IGAIN = 'lily_pid_coeff_igain'
    PID_PGAIN = 'lily_pid_coeff_pgain'
    PID_DGAIN = 'lily_pid_coeff_dgain'
    MOTOR_ILIMIT = 'lily_motor_current_limit'
    MOTOR_ILIMIT_UNITS = 'lily_motor_current_limit_units'
    SUPPLY_VOLTAGE = 'supply_voltage'
    MEM_SAVE_MODE = 'lily_memory_save_mode'
    OUTPUTTING_DATA = 'lily_outputting_data'
    RECOVERY_MODE = 'lily_auto_power_off_recovery_mode'
    ADV_MEM_MODE = 'lily_advanced_memory_mode'
    DEL_W_XYMEMD = 'lily_delete_with_xy_memd'


# noinspection PyMethodMayBeStatic
class LILYStatus02Particle(BotptStatus02Particle):
    _data_particle_type = DataParticleType.LILY_STATUS_02
    # Example of output from DUMP2 command:
    # covered by base class
    # LILY,2013/06/24 23:36:05,*01: TBias: 5.00
    # LILY,2013/06/24 23:36:05,*01: Above 0.00(KZMinTemp): kz[0]=           0, kz[1]=           0
    # LILY,2013/06/24 23:36:05,*01: Below 0.00(KZMinTemp): kz[2]=           0, kz[3]=           0
    # LILY,2013/06/24 23:36:05,*01: ADCDelay:  310
    # LILY,2013/06/24 23:36:05,*01: PCA Model: 84833-14
    # LILY,2013/06/24 23:36:05,*01: Firmware Version: 2.1 Rev D
    # LILY,2013/06/24 23:36:05,*01: X Ch Gain= 1.0000, Y Ch Gain= 1.0000, Temperature Gain= 1.0000
    # LILY,2013/06/24 23:36:05,*01: Calibrated in uRadian, Current Output Mode: uRadian
    # LILY,2013/06/24 23:36:05,*01: Using RS232
    # LILY,2013/06/24 23:36:05,*01: Real Time Clock: Installed
    # LILY,2013/06/24 23:36:05,*01: Use RTC for Timing: Yes
    # LILY,2013/06/24 23:36:05,*01: External Flash: 2162688 Bytes Installed
    # LILY,2013/06/24 23:36:05,*01: Calibration method: Dynamic
    # LILY,2013/06/24 23:36:05,*01: Positive Limit=330.00   Negative Limit=-330.00
    # LILY,2013/06/24 23:36:05,*01: Calibration Points:023  X: Enabled  Y: Enabled
    # LILY,2013/06/24 23:36:05,*01: ADC: 16-bit(external)
    # implemented here
    # LILY,2013/06/24 23:36:05,*01: Flash Status (in Samples) (Used/Total): (-1/55424)
    # LILY,2013/06/24 23:36:05,*01: Low Power Logger Data Rate: -1 Seconds per Sample
    # LILY,2013/06/24 23:36:05,*01: Uniaxial (x2) Sensor Type (1)
    # LILY,2013/06/24 23:36:05,*01: Compass: Installed   Magnetic Declination: 0.000000
    # LILY,2013/06/24 23:36:05,*01: Compass: Xoffset:   12, Yoffset:  210, Xrange: 1371, Yrange: 1307
    # LILY,2013/06/24 23:36:05,*01: PID Coeff: iMax:100.0, iMin:-100.0, iGain:0.0150, pGain: 2.50, dGain: 10.0
    # LILY,2013/06/24 23:36:05,*01: Motor I_limit: 90.0mA
    # LILY,2013/06/24 23:36:05,*01: Current Time: 01/11/00 02:12:32
    # LILY,2013/06/24 23:36:06,*01: Supply Voltage: 11.96 Volts
    # LILY,2013/06/24 23:36:06,*01: Memory Save Mode: Off
    # LILY,2013/06/24 23:36:06,*01: Outputting Data: Yes
    # LILY,2013/06/24 23:36:06,*01: Auto Power-Off Recovery Mode: Off
    # LILY,2013/06/24 23:36:06,*01: Advanced Memory Mode: Off, Delete with XY-MEMD: No

    _encoders = BotptStatus02Particle._encoders
    _encoders.update({
        LILYStatus02ParticleKey.TOTAL_SAMPLES: int,
        LILYStatus02ParticleKey.USED_SAMPLES: int,
        LILYStatus02ParticleKey.LOW_POWER_RATE: int,
        LILYStatus02ParticleKey.COMPASS_INSTALLED: str,
        LILYStatus02ParticleKey.COMPASS_XOFFSET: int,
        LILYStatus02ParticleKey.COMPASS_YOFFSET: int,
        LILYStatus02ParticleKey.COMPASS_XRANGE: int,
        LILYStatus02ParticleKey.COMPASS_YRANGE: int,
        LILYStatus02ParticleKey.MOTOR_ILIMIT_UNITS: str,
        LILYStatus02ParticleKey.MEM_SAVE_MODE: str,
        LILYStatus02ParticleKey.OUTPUTTING_DATA: str,
        LILYStatus02ParticleKey.RECOVERY_MODE: str,
        LILYStatus02ParticleKey.ADV_MEM_MODE: str,
        LILYStatus02ParticleKey.DEL_W_XYMEMD: str,
    })

    @classmethod
    def _regex_multiline(cls):
        sub_dict = {
            'float': cls.floating_point_num,
            'four_floats': cls.four_floats,
            'six_floats': cls.six_floats,
            'int': cls.integer,
            'word': cls.word,
        }
        regex_dict = {
            LILYStatus02ParticleKey.TOTAL_SAMPLES: r'\(Used/Total\): \(.*?/%(int)s\)' % sub_dict,
            LILYStatus02ParticleKey.USED_SAMPLES: r'\(Used/Total\): \(%(int)s/.*?\)' % sub_dict,
            LILYStatus02ParticleKey.LOW_POWER_RATE: r'Low Power Logger Data Rate: %(int)s' % sub_dict,
            LILYStatus02ParticleKey.COMPASS_INSTALLED: r'Compass: %(word)s' % sub_dict,
            LILYStatus02ParticleKey.COMPASS_MAG_DECL: r'Magnetic Declination: %(float)s' % sub_dict,
            LILYStatus02ParticleKey.COMPASS_XOFFSET: r'Compass: Xoffset:\s*%(int)s' % sub_dict,
            LILYStatus02ParticleKey.COMPASS_YOFFSET: r'Compass:.*Yoffset:\s*%(int)s' % sub_dict,
            LILYStatus02ParticleKey.COMPASS_XRANGE: r'Compass:.*Xrange:\s*%(int)s' % sub_dict,
            LILYStatus02ParticleKey.COMPASS_YRANGE: r'Compass:.*Yrange:\s*%(int)s' % sub_dict,
            LILYStatus02ParticleKey.PID_IMAX: r'PID.*iMax:\s*%(float)s' % sub_dict,
            LILYStatus02ParticleKey.PID_IMIN: r'PID.*iMin:\s*%(float)s' % sub_dict,
            LILYStatus02ParticleKey.PID_IGAIN: r'PID.*iGain:\s*%(float)s' % sub_dict,
            LILYStatus02ParticleKey.PID_PGAIN: r'PID.*pGain:\s*%(float)s' % sub_dict,
            LILYStatus02ParticleKey.PID_DGAIN: r'PID.*dGain:\s*%(float)s' % sub_dict,
            LILYStatus02ParticleKey.MOTOR_ILIMIT: r'Motor I_limit: %(float)s' % sub_dict,
            LILYStatus02ParticleKey.MOTOR_ILIMIT_UNITS: r'Motor I_limit: [0-9\.\-]*%(word)s' % sub_dict,
            LILYStatus02ParticleKey.SUPPLY_VOLTAGE: r'Supply Voltage: %(float)s' % sub_dict,
            LILYStatus02ParticleKey.MEM_SAVE_MODE: r'Memory Save Mode: %(word)s' % sub_dict,
            LILYStatus02ParticleKey.OUTPUTTING_DATA: r'Outputting Data: %(word)s' % sub_dict,
            LILYStatus02ParticleKey.RECOVERY_MODE: r'Auto Power-Off Recovery Mode: %(word)s' % sub_dict,
            LILYStatus02ParticleKey.ADV_MEM_MODE: r'Advanced Memory Mode: %(word)s,' % sub_dict,
            LILYStatus02ParticleKey.DEL_W_XYMEMD: r'Delete with XY-MEMD: %(word)s' % sub_dict,
        }
        regex_dict.update(BotptStatus02Particle._regex_multiline())
        return regex_dict


###############################################################################
# Leveling Particles
###############################################################################


class LILYLevelingParticleKey(BaseEnum):
    SENSOR_ID = "sensor_id"
    TIME = "date_time_string"
    X_TILT = "lily_x_tilt"
    Y_TILT = "lily_y_tilt"
    MAG_COMPASS = "compass_direction"
    TEMP = "lily_temp"
    SUPPLY_VOLTS = "supply_voltage"
    SN = "serial_number"
    STATUS = "lily_leveling_status"


class LILYLevelingParticle(DataParticle):
    _data_particle_type = DataParticleType.LILY_LEVELING
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
        status = 'Leveling'

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

# noinspection PyMethodMayBeStatic
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
        self._protocol = Protocol(BaseEnum, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

# noinspection PyUnusedLocal,PyMethodMayBeStatic
class Protocol(BotptProtocol):
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
        BotptProtocol.__init__(self, prompts, newline, driver_event)

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
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status),
                (ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample),
                (ProtocolEvent.START_LEVELING, self._handler_autosample_start_leveling),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_command_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status),
                (ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample),
                (ProtocolEvent.START_LEVELING, self._handler_command_start_leveling),
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
                (ProtocolEvent.EXIT, self._handler_leveling_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.STOP_LEVELING, self._handler_stop_leveling),
                (ProtocolEvent.LEVELING_TIMEOUT, self._handler_leveling_timeout),
            ],
            ProtocolState.AUTOSAMPLE_LEVELING: [
                (ProtocolEvent.ENTER, self._handler_leveling_enter),
                (ProtocolEvent.EXIT, self._handler_leveling_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.STOP_LEVELING, self._handler_stop_leveling),
                (ProtocolEvent.LEVELING_TIMEOUT, self._handler_leveling_timeout),
            ]
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCommand.DATA_ON, self._build_command)
        self._add_build_handler(InstrumentCommand.DATA_OFF, self._build_command)
        self._add_build_handler(InstrumentCommand.DUMP_SETTINGS_01, self._build_command)
        self._add_build_handler(InstrumentCommand.DUMP_SETTINGS_02, self._build_command)
        self._add_build_handler(InstrumentCommand.START_LEVELING, self._build_command)
        self._add_build_handler(InstrumentCommand.STOP_LEVELING, self._build_command)

        # # Add response handlers for device commands.
        for command in InstrumentCommand.list():
            self._add_response_handler(command, self._resp_handler)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

        # set up the regexes now so we don't have to do it repeatedly
        self.data_regex = LILYDataParticle.regex_compiled()
        self.status_01_regex = LILYStatus01Particle.regex_compiled()
        self.status_02_regex = LILYStatus02Particle.regex_compiled()
        self.leveling_regex = LILYLevelingParticle.regex_compiled()

        self._last_data_timestamp = 0
        self._filter_string = LILY_STRING

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

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="start autosample")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="stop autosample")
        self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name="acquire status")
        self._cmd_dict.add(Capability.START_LEVELING, display_name="start leveling")
        self._cmd_dict.add(Capability.STOP_LEVELING, display_name="stop leveling")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        my_regex = 'Not used'
        ro, rw = ParameterDictVisibility.READ_ONLY, ParameterDictVisibility.READ_WRITE
        _bool, _float, _int = ParameterDictType.BOOL, ParameterDictType.FLOAT, ParameterDictType.INT
        parameters = [
            (Parameter.AUTO_RELEVEL, _bool, 'Automatic releveling enabled', rw),
            (Parameter.XTILT_TRIGGER, _float, 'X-tilt releveling trigger', rw),
            (Parameter.YTILT_TRIGGER, _float, 'Y-tilt releveling trigger', rw),
            (Parameter.LEVELING_TIMEOUT, _int, 'LILY leveling timeout', rw),
            (Parameter.LEVELING_FAILED, _bool, 'LILY leveling failed', ro),
        ]
        for param, param_type, param_name, param_vis in parameters:
            self._param_dict.add(param, my_regex, None, None, type=param_type,
                                 visibility=param_vis, display_name=param_name)

        self._param_dict.set_value(Parameter.LEVELING_FAILED, False)

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

    def _resp_handler(self, response, prompt):
        log.debug('_resp_handler - response: %r prompt: %r', response, prompt)
        return response

    def _extract_sample(self, particle_class, regex, line, timestamp, publish=True):
        """
        Overridden _extract_sample to provide the value of LEVELING_FAILED when producing
        autosample particles (LILYDataParticle)
        """
        sample = None
        if regex.match(line):
            if particle_class == LILYDataParticle:
                particle = particle_class(line, port_timestamp=timestamp,
                                          out_of_range=self._param_dict.get(Parameter.LEVELING_FAILED))
            else:
                particle = particle_class(line, port_timestamp=timestamp)
            parsed_sample = particle.generate()

            if publish and self._driver_event:
                self._driver_event(DriverAsyncEvent.SAMPLE, parsed_sample)

            sample = json.loads(parsed_sample)

        return sample

    def _check_for_autolevel(self, sample):
        if self._param_dict.get(Parameter.AUTO_RELEVEL) and self.get_current_state() == ProtocolState.AUTOSAMPLE:
            # Find the current X and Y tilt values
            # If they exceed the trigger parameters, begin autolevel
            relevel = False
            values = sample.get(DataParticleKey.VALUES, [])
            for each in values:
                value_id = each.get(DataParticleKey.VALUE_ID)
                value = each.get(DataParticleKey.VALUE)
                if value_id == LILYDataParticleKey.X_TILT:
                    if abs(value) > self._param_dict.get(Parameter.XTILT_TRIGGER):
                        relevel = True
                        break
                elif value_id == LILYDataParticleKey.Y_TILT:
                    if abs(value) > self._param_dict.get(Parameter.YTILT_TRIGGER):
                        relevel = True
                        break
            if relevel:
                self._async_raise_fsm_event(ProtocolEvent.START_LEVELING)

    def _failed_leveling(self, axis):
        log.error('Detected leveling error in %s axis!', axis)
        # Read only parameter, must be set outside of handler
        self._param_dict.set_value(Parameter.LEVELING_FAILED, True)
        # Use the handler to disable auto relevel to raise a config change event if needed.
        self._handler_command_set({Parameter.AUTO_RELEVEL: False})
        raise InstrumentDataException('LILY Leveling (%s) Failed.  Disabling auto relevel' % axis)

    def _check_completed_leveling(self, sample):
        values = sample.get(DataParticleKey.VALUES, [])
        for each in values:
            value_id = each.get(DataParticleKey.VALUE_ID)
            value = each.get(DataParticleKey.VALUE)
            if value_id == LILYLevelingParticleKey.STATUS:
                if value is not None:
                    # Leveling status update received
                    # If leveling complete, send STOP_LEVELING, set the _leveling_failed flag to False
                    if 'Leveled' in value:
                        if self._param_dict.get(Parameter.LEVELING_FAILED):
                            self._handler_command_set({Parameter.LEVELING_FAILED: False})
                            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
                        self._async_raise_fsm_event(ProtocolEvent.STOP_LEVELING)
                    # Leveling X failed!  Set the flag and raise an exception to notify the operator
                    # and disable auto leveling. Let the instrument attempt to level
                    # in the Y axis.
                    elif 'X Axis out of range' in value:
                        self._failed_leveling('X')
                    # Leveling X failed!  Set the flag and raise an exception to notify the operator
                    # and disable auto leveling. Send STOP_LEVELING
                    elif 'Y Axis out of range' in value:
                        self._async_raise_fsm_event(ProtocolEvent.STOP_LEVELING)
                        self._failed_leveling('Y')

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, result)
        """
        # Attempt to find a line containing a LILY sample or leveling response
        # If leveling, STOP leveling and return to command (cannot verify leveling state)
        # If a sample is found, go to AUTOSAMPLE, otherwise COMMAND
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.IDLE
        result = None
        try:
            # clear out the buffers to ensure we are getting new data
            # this is necessary when discovering out of direct access.
            self._promptbuf = ''
            self._linebuf = ''
            response = self._get_response(timeout=2, response_regex=DISCOVER_REGEX)[0]
            log.debug('_handler_unknown_discover: response: [%r]', response)
            # autosample
            if LILYDataParticle.regex_compiled().search(response):
                next_state = ProtocolState.AUTOSAMPLE
                next_agent_state = ResourceAgentState.STREAMING
            # leveling - stop leveling, return to COMMAND
            elif LILYLevelingParticle.regex_compiled().search(response):
                self._handler_stop_leveling()
        # timed out, assume command
        except InstrumentTimeoutException:
            log.debug('_handler_unknown_discover: no LILY data found, going to COMMAND')
        log.debug('_handler_unknown_discover: returning: %r', (next_state, next_agent_state))
        return next_state, next_agent_state

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_stop_autosample(self):
        """
        Turn the lily data off
        """
        return self._handler_command_generic(InstrumentCommand.DATA_OFF,
                                             ProtocolState.COMMAND,
                                             ResourceAgentState.COMMAND,
                                             expected_prompt=LILY_DATA_OFF)

    def _handler_autosample_start_leveling(self, *args, **kwargs):
        """
        Put instrument into leveling mode
        """
        return self._handler_command_generic(InstrumentCommand.START_LEVELING,
                                             ProtocolState.AUTOSAMPLE_LEVELING,
                                             ResourceAgentState.BUSY,
                                             expected_prompt=LILY_LEVEL_ON)

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Turn the lily data on
        """
        return self._handler_command_generic(InstrumentCommand.DATA_ON,
                                             ProtocolState.AUTOSAMPLE,
                                             ResourceAgentState.STREAMING,
                                             expected_prompt=LILY_DATA_ON)

    def _handler_command_start_leveling(self, *args, **kwargs):
        """
        Put instrument into leveling mode
        """
        return self._handler_command_generic(InstrumentCommand.START_LEVELING,
                                             ProtocolState.COMMAND_LEVELING,
                                             ResourceAgentState.BUSY,
                                             expected_prompt=LILY_LEVEL_ON)

    ########################################################################
    # Leveling Handlers
    ########################################################################

    def _handler_leveling_enter(self, *args, **kwargs):
        """
        Set up a leveling timer to make sure we don't stay in
        leveling state forever if something goes wrong
        """
        log.debug("_handler_leveling_enter")

        job_name = ScheduledJob.LEVELING_TIMEOUT
        config = {
            DriverConfigKey.SCHEDULER: {
                job_name: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.SECONDS: self._param_dict.get(Parameter.LEVELING_TIMEOUT)
                    },
                }
            }
        }

        self.set_init_params(config)
        self._add_scheduler_event(ScheduledJob.LEVELING_TIMEOUT, ProtocolEvent.LEVELING_TIMEOUT)

    def _handler_stop_leveling(self, *args, **kwargs):
        """
        Take instrument out of leveling mode, returning to the previous state
        """
        log.debug('enter _handler_stop_leveling')
        _, (_, result) = self._handler_command_generic(InstrumentCommand.STOP_LEVELING, None, None,
                                                       expected_prompt=LILY_LEVEL_OFF)
        if self.get_current_state() == ProtocolState.AUTOSAMPLE_LEVELING:
            next_state, (next_agent_state, result) = self._handler_command_start_autosample()
        else:
            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.COMMAND
        log.debug('exit _handler_stop_leveling: next_state: %s next_agent_state: %s', next_state, next_agent_state)
        self._async_agent_state_change(next_agent_state)
        return next_state, (next_agent_state, result)

    def _handler_leveling_exit(self, *args, **kwargs):
        try:
            self._remove_scheduler(ScheduledJob.LEVELING_TIMEOUT)
        except KeyError:
            log.error("_remove_scheduler could not find: %s", ScheduledJob.LEVELING_TIMEOUT)

    def _handler_leveling_timeout(self):
        """
        The LILY leveling operation has timed out.
        Set the leveling failed flag, disable autolevel and raise an exception
        """
        log.debug('_handler_leveling_timeout')
        # set this directly, as it is a read only value
        self._param_dict.set_value(Parameter.LEVELING_FAILED, True)
        # set this through the handler to allow for change event to be raised.
        self._handler_command_set({Parameter.AUTO_RELEVEL: False})
        self._async_raise_fsm_event(ProtocolEvent.STOP_LEVELING)
        raise InstrumentDataException('LILY Leveling timed out, Disabling auto relevel.')

    ########################################################################
    # Handlers common to Command and Autosample States.
    ########################################################################

    def _handler_command_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        log.debug("_handler_command_autosample_acquire_status")
        _, (_, result1) = self._handler_command_generic(InstrumentCommand.DUMP_SETTINGS_01,
                                                        None, None, expected_prompt=LILY_DUMP_01)
        _, (_, result2) = self._handler_command_generic(InstrumentCommand.DUMP_SETTINGS_02,
                                                        None, None, expected_prompt=LILY_DUMP_02)
        return None, (None, '%s %s' % (result1, result2))