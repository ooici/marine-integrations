"""
@package mi.instrument.seabird.sbe26plus_v2.driver
@file mi/instrument/seabird/sbe16plus_v2/driver.py
@author David Everett 
@brief Driver base class for sbe16plus V2 CTD instrument.
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import time
import datetime
import re
import string
from threading import Timer

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.time import get_timestamp_delayed
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import ResourceAgentEvent
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue, CommonDataParticleType
from mi.core.instrument.protocol_param_dict import ParameterDictVal
from mi.core.instrument.chunker import StringChunker
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException

from mi.instrument.seabird.driver import SeaBirdInstrumentDriver
from mi.instrument.seabird.driver import SeaBirdParticle
from mi.instrument.seabird.driver import SeaBirdProtocol
from mi.instrument.seabird.driver import NEWLINE
from mi.instrument.seabird.driver import TIMEOUT
from mi.instrument.seabird.driver import DEFAULT_ENCODER_KEY

###############################################################################
# Module-wide values
###############################################################################

###############################################################################
# Static enumerations for this class
###############################################################################

ERROR_PATTERN = r"<ERROR type='(.*?)' msg='(.*?)'\/>"
ERROR_REGEX   = re.compile(ERROR_PATTERN, re.DOTALL)

LOGGING_PATTERN = r'<LoggingState>(.*?)</LoggingState>'
LOGGING_REGEX = re.compile(LOGGING_PATTERN, re.DOTALL)

class ScheduledJob(BaseEnum):
    ACQUIRE_STATUS = 'acquire_status'
    CONFIGURATION_DATA = "configuration_data"
    CLOCK_SYNC = 'clock_sync'

class Command(BaseEnum):
        DS  = 'ds'
        DCAL = 'dcal' # DHE dcal replaces dc
        TS = 'ts'
        STARTNOW = 'startnow'
        STOP = 'stop'
        TC = 'tc'
        TT = 'tt'
        TP = 'tp'
        SET = 'set'
        GETCD = 'getcd'
        GETSD = 'getsd'
        QS = 'qs'
        RESET_EC = 'ResetEC'

class ProtocolState(BaseEnum):
    """
    Protocol states for SBE16. Cherry picked from DriverProtocolState
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    TEST = DriverProtocolState.TEST
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    
class ProtocolEvent(BaseEnum):
    """
    Protocol events for SBE16. Cherry picked from DriverEvent enum.
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    GET_CONFIGURATION = 'PROTOCOL_EVENT_GET_CONFIGURATION'
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    TEST = DriverEvent.TEST
    RUN_TEST = DriverEvent.RUN_TEST
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    SCHEDULED_CLOCK_SYNC = DriverEvent.SCHEDULED_CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    QUIT_SESSION = 'PROTOCOL_EVENT_QUIT_SESSION'
    RESET_EC = 'PROTOCOL_EVENT_RESET_EC'

class Capability(BaseEnum):
    """
    Capabilities that are exposed to the user (subset of above)
    """
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    QUIT_SESSION = ProtocolEvent.QUIT_SESSION
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    GET_CONFIGURATION = ProtocolEvent.GET_CONFIGURATION
    TEST = DriverEvent.TEST
    DISCOVER = DriverEvent.DISCOVER
    RESET_EC = ProtocolEvent.RESET_EC

# Device specific parameters.
class Parameter(DriverParameter):
    """
    Device parameters for SBE16.
    """
    INTERVAL = 'SampleInterval'
    TXREALTIME = 'TXREALTIME'
    DATE_TIME = "DateTime"
    LOGGING = "logging"
    ECHO = "echo"
    OUTPUT_EXEC_TAG = 'OutputExecutedTag'
    PUMP_MODE = "PumpMode"
    NCYCLES = "NCycles"
    BIOWIPER = "Biowiper"
    PTYPE = "PType"
    VOLT0 = "Volt0"
    VOLT1 = "Volt1"
    VOLT2 = "Volt2"
    VOLT3 = "Volt3"
    VOLT4 = "Volt4"
    VOLT5 = "Volt5"
    DELAY_BEFORE_SAMPLE = "DelayBeforeSampling"
    DELAY_AFTER_SAMPLE = "DelayAfterSampling"
    SBE63 = "SBE63"
    SBE38 = "SBE38"
    SBE50 = "SBE50"
    WETLABS = "WetLabs"
    GTD = "GTD"
    OPTODE = "OPTODE"
    SYNCMODE = "SyncMode"
    SYNCWAIT = "SyncWait"
    OUTPUT_FORMAT = "OutputFormat"

class ConfirmedParameter(BaseEnum):
    """
    List of all parameters that require confirmation
    i.e. set sent twice to confirm.
    """
    PTYPE    =  Parameter.PTYPE
    SBE63    =  Parameter.SBE63
    SBE38    =  Parameter.SBE38
    SBE50    =  Parameter.SBE50
    GTD      =  Parameter.GTD
    OPTODE   =  Parameter.OPTODE
    WETLABS  =  Parameter.WETLABS
    VOLT0    =  Parameter.VOLT0
    VOLT1    =  Parameter.VOLT1
    VOLT2    =  Parameter.VOLT2
    VOLT3    =  Parameter.VOLT3
    VOLT4    =  Parameter.VOLT4
    VOLT5    =  Parameter.VOLT5

# Device prompts.
class Prompt(BaseEnum):
    """
    SBE16 io prompts.
    """
    COMMAND = 'S>'
    BAD_COMMAND = '?cmd S>'
    AUTOSAMPLE = 'S>'
    EXECUTED = '<Executed/>'

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    CTD_PARSED = 'ctdbp_cdef_sample'
    DEVICE_STATUS = 'ctdbp_cdef_status'
    DEVICE_CALIBRATION = 'ctdbp_cdef_calibration_coefficients'

class SBE16DataParticleKey(BaseEnum):
    TEMP = "temperature"
    CONDUCTIVITY = "conductivity"
    PRESSURE = "pressure"
    PRESSURE_TEMP = "pressure_temp"
    TIME = "ctd_time"

class SBE16DataParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Sample:
       #03EC1F0A738A81736187100004000B2CFDC618B859BE

    Format:
       #ttttttccccccppppppvvvvvvvvvvvvssssssss

       Temperature = tttttt = 0A5371 (676721 decimal); temperature A/D counts = 676721
       Conductivity = 1BC722 (1820450 decimal); conductivity frequency = 1820450 / 256 = 7111.133 Hz
       Internally mounted strain gauge pressure = pppppp = 0C14C1 (791745 decimal);
           Strain gauge pressure A/D counts = 791745
       Internally mounted strain gauge temperature compensation = vvvv = 7D82 (32,130 decimal);
           Strain gauge temperature = 32,130 / 13,107 = 2.4514 volts
       First external voltage = vvvv = 0305 (773 decimal); voltage = 773 / 13,107 = 0.0590 volts
       Second external voltage = vvvv = 0594 (1428 decimal); voltage = 1428 / 13,107 = 0.1089 volts
       Time = ssssssss = 0EC4270B (247,736,075 decimal); seconds since January 1, 2000 = 247,736,075
    """
    _data_particle_type = DataParticleType.CTD_PARSED

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        #ttttttccccccppppppvvvvvvvvvvvvssssssss
        pattern = r'#? *' # patter may or may not start with a '
        pattern += r'([0-9A-F]{6})' # temperature
        pattern += r'([0-9A-F]{6})' # conductivity
        pattern += r'([0-9A-F]{6})' # pressure
        pattern += r'([0-9A-F]{4})' # pressure temp
        pattern += r'[0-9A-F]*' # consume extra voltage measurements
        pattern += r'([0-9A-F]{8})' # time
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(SBE16DataParticle.regex())

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = SBE16DataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)
            
        try:
            temperature = self.hex2value(match.group(1))
            conductivity = self.hex2value(match.group(2))
            pressure = self.hex2value(match.group(3))
            pressure_temp = self.hex2value(match.group(4))
            elapse_time = self.hex2value(match.group(5))

            self.set_internal_timestamp(unix_time=self.sbetime2unixtime(elapse_time))
        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)
        
        result = [{DataParticleKey.VALUE_ID: SBE16DataParticleKey.TEMP,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: SBE16DataParticleKey.CONDUCTIVITY,
                   DataParticleKey.VALUE: conductivity},
                  {DataParticleKey.VALUE_ID: SBE16DataParticleKey.PRESSURE,
                    DataParticleKey.VALUE: pressure},
                  {DataParticleKey.VALUE_ID: SBE16DataParticleKey.PRESSURE_TEMP,
                   DataParticleKey.VALUE: pressure_temp},
                  {DataParticleKey.VALUE_ID: SBE16DataParticleKey.TIME,
                    DataParticleKey.VALUE: elapse_time}]
        
        return result

class SBE16StatusParticleKey(BaseEnum):
    FIRMWARE_VERSION = "firmware_version"
    SERIAL_NUMBER = "serial_number"
    DATE_TIME = "date_time_string"
    VBATT = "battery_voltage_main"
    VLITH = "battery_voltage_lithium"
    IOPER = "operational_current"
    IPUMP = "pump_current"
    STATUS = "logging_status"
    SAMPLES = "num_samples"
    FREE = "mem_free"
    SAMPLE_INTERVAL = "sample_interval"
    MEASUREMENTS_PER_SAMPLE = "measurements_per_sample"
    PUMP_MODE = "pump_mode"
    DELAY_BEFORE_SAMPLING = "delay_before_sampling"
    DELAY_AFTER_SAMPLING = "delay_after_sampling"
    TX_REAL_TIME = "tx_real_time"
    BATTERY_CUTOFF = "battery_cutoff"
    PRESSURE_SENSOR = "pressure_sensor_type"
    RANGE = "pressure_sensor_range"
    SBE38 = "sbe38"
    SBE50 = "sbe50"
    WETLABS = "wetlabs"
    OPTODE = "optode"
    GAS_TENSION_DEVICE = "gas_tension_device"
    EXT_VOLT_0 = "ext_volt_0"
    EXT_VOLT_1 = "ext_volt_1"
    EXT_VOLT_2 = "ext_volt_2"
    EXT_VOLT_3 = "ext_volt_3"
    EXT_VOLT_4 = "ext_volt_4"
    EXT_VOLT_5 = "ext_volt_5"
    ECHO_CHARACTERS = "echo_characters"
    OUTPUT_FORMAT = "output_format"
    OUTPUT_SALINITY = "output_salinity"
    OUTPUT_SOUND_VELOCITY = "output_sound_velocity"
    SERIAL_SYNC_MODE = "serial_sync_mode"

class SBE16StatusParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_STATUS

    @staticmethod
    def regex():
        # pattern for the first line of the 'ds' command
        pattern =  r'SBE 16plus'
        pattern += r'.*?' # non-greedy match of all the junk between
        pattern += r'serial sync mode (disabled|enabled)' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE16StatusParticle.regex(), re.DOTALL)

    def encoders(self):
        return {
            DEFAULT_ENCODER_KEY: str,

            SBE16StatusParticleKey.SERIAL_NUMBER : int,
            SBE16StatusParticleKey.VBATT : float,
            SBE16StatusParticleKey.VLITH : float,
            SBE16StatusParticleKey.IOPER : float,
            SBE16StatusParticleKey.IPUMP : float,
            SBE16StatusParticleKey.SAMPLES : int,
            SBE16StatusParticleKey.SAMPLE_INTERVAL : int,
            SBE16StatusParticleKey.FREE : int,
            SBE16StatusParticleKey.MEASUREMENTS_PER_SAMPLE : int,
            SBE16StatusParticleKey.DELAY_BEFORE_SAMPLING : float,
            SBE16StatusParticleKey.DELAY_AFTER_SAMPLING : float,
            SBE16StatusParticleKey.TX_REAL_TIME : self.yesno2bool,
            SBE16StatusParticleKey.BATTERY_CUTOFF : float,
            SBE16StatusParticleKey.RANGE : float,
            SBE16StatusParticleKey.SBE38 : self.yesno2bool,
            SBE16StatusParticleKey.SBE50 : self.yesno2bool,
            SBE16StatusParticleKey.WETLABS : self.yesno2bool,
            SBE16StatusParticleKey.OPTODE : self.yesno2bool,
            SBE16StatusParticleKey.GAS_TENSION_DEVICE : self.yesno2bool,
            SBE16StatusParticleKey.EXT_VOLT_0 : self.yesno2bool,
            SBE16StatusParticleKey.EXT_VOLT_1 : self.yesno2bool,
            SBE16StatusParticleKey.EXT_VOLT_2 : self.yesno2bool,
            SBE16StatusParticleKey.EXT_VOLT_3 : self.yesno2bool,
            SBE16StatusParticleKey.EXT_VOLT_4 : self.yesno2bool,
            SBE16StatusParticleKey.EXT_VOLT_5 : self.yesno2bool,
            SBE16StatusParticleKey.ECHO_CHARACTERS : self.yesno2bool,
            SBE16StatusParticleKey.OUTPUT_FORMAT : SBE16Protocol._output_format_string_2_int,
            SBE16StatusParticleKey.OUTPUT_SALINITY : self.yesno2bool,
            SBE16StatusParticleKey.OUTPUT_SOUND_VELOCITY : self.yesno2bool,
            SBE16StatusParticleKey.SERIAL_SYNC_MODE : self.disabled2bool,
        }

    def regex_multiline(self):
        '''
            SBE 16plus V 2.5  SERIAL NO. 7231    25 Feb 2013 16:31:28
            vbatt = 13.3, vlith =  8.5, ioper =  51.1 ma, ipump =   0.3 ma,
            iext01 =   0.4 ma, iserial =  45.6 ma
            status = not logging
            samples = 0, free = 2990824
            sample interval = 10 seconds, number of measurements per sample = 4
            Paros integration time = 1.0 seconds
            pump = run pump during sample, delay before sampling = 0.0 seconds, delay after sampling = 0.0 seconds
            transmit real-time = yes
            battery cutoff =  7.5 volts
            pressure sensor = quartz with temp comp, range = 1000.0
            SBE 38 = no, SBE 50 = no, WETLABS = no, OPTODE = yes, SBE63 = no, Gas Tension Device = no
            Ext Volt 0 = yes, Ext Volt 1 = yes
            Ext Volt 2 = no, Ext Volt 3 = no
            Ext Volt 4 = no, Ext Volt 5 = no
            echo characters = yes
            output format = raw HEX
            serial sync mode disabled
        '''
        return {
            SBE16StatusParticleKey.FIRMWARE_VERSION : r'SBE 16plus V *(\d+.\d+) ',
            SBE16StatusParticleKey.SERIAL_NUMBER : r'SERIAL NO. *(\d+) ',
            SBE16StatusParticleKey.DATE_TIME : r'(\d{1,2} [\w]{3} \d{4} [\d:]+)',
            SBE16StatusParticleKey.VBATT : r'vbatt = *(\d+.\d+),',
            SBE16StatusParticleKey.VLITH : r'vlith = *(\d+.\d+),',
            SBE16StatusParticleKey.IOPER : r'ioper = *(\d+.\d+) [a-zA-Z]+',
            SBE16StatusParticleKey.IPUMP : r'ipump = *(\d+.\d+) [a-zA-Z]+',
            SBE16StatusParticleKey.STATUS : r'status = *(.*)',
            SBE16StatusParticleKey.SAMPLES : r'samples = *(\d+)',
            SBE16StatusParticleKey.FREE : r'free = *(\d+)',
            SBE16StatusParticleKey.SAMPLE_INTERVAL : r'sample interval = *(\d+)',
            SBE16StatusParticleKey.MEASUREMENTS_PER_SAMPLE :  r'number of measurements per sample = (\d+)',
            SBE16StatusParticleKey.PUMP_MODE :  r'^pump = ([ \w]+),',
            SBE16StatusParticleKey.DELAY_BEFORE_SAMPLING : r'delay before sampling = (\d+.\d+) \w+',
            SBE16StatusParticleKey.DELAY_AFTER_SAMPLING : r'delay after sampling = (\d+.\d+) \w+',
            SBE16StatusParticleKey.TX_REAL_TIME : r'transmit real-time = (\w+) *',
            SBE16StatusParticleKey.BATTERY_CUTOFF : r'battery cutoff =\s+(\d+.\d+) \w+',
            SBE16StatusParticleKey.PRESSURE_SENSOR : r'pressure sensor = ([\s\w]+), range =',
            SBE16StatusParticleKey.RANGE : r'range = (\d+.\d+)',
            SBE16StatusParticleKey.SBE38 : r'SBE 38 = (\w+)',
            SBE16StatusParticleKey.SBE50 : r'SBE 50 = (\w+)',
            SBE16StatusParticleKey.WETLABS : r'WETLABS = (\w+)',
            SBE16StatusParticleKey.OPTODE : r'OPTODE = (\w+)',
            SBE16StatusParticleKey.GAS_TENSION_DEVICE : r'Gas Tension Device = (\w+)',
            SBE16StatusParticleKey.EXT_VOLT_0 : r'Ext Volt 0 = (yes|no)',
            SBE16StatusParticleKey.EXT_VOLT_1 : r'Ext Volt 1 = (yes|no)',
            SBE16StatusParticleKey.EXT_VOLT_2 : r'Ext Volt 2 = (yes|no)',
            SBE16StatusParticleKey.EXT_VOLT_3 : r'Ext Volt 3 = (yes|no)',
            SBE16StatusParticleKey.EXT_VOLT_4 : r'Ext Volt 4 = (yes|no)',
            SBE16StatusParticleKey.EXT_VOLT_5 : r'Ext Volt 5 = (yes|no)',
            SBE16StatusParticleKey.ECHO_CHARACTERS : r'echo characters = (\w+)',
            SBE16StatusParticleKey.OUTPUT_FORMAT : r'output format = ([\s\w]+)',
            SBE16StatusParticleKey.OUTPUT_SALINITY : r'output salinity = (\w+)',
            SBE16StatusParticleKey.OUTPUT_SOUND_VELOCITY : r'output sound velocity = (\w+)',
            SBE16StatusParticleKey.SERIAL_SYNC_MODE : r'serial sync mode (\w+)',
        }

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = SBE16StatusParticle.regex_compiled().match(self.raw_data)
        
        if not match:
            raise SampleException("No regex match of parsed status data: [%s]" %
                                  self.raw_data)

        try:
            return self._get_multiline_values()
        except ValueError as e:
            raise SampleException("ValueError while decoding status: [%s]" % e)


class SBE16CalibrationParticleKey(BaseEnum):
    FIRMWARE_VERSION = "firmware_version"
    SERIAL_NUMBER = "serial_number"
    DATE_TIME = "date_time_string"
    TEMP_CAL_DATE = "calibration_date_temperature"
    TA0 = "temp_coeff_ta0"
    TA1 = "temp_coeff_ta1"
    TA2 = "temp_coeff_ta2"
    TA3 = "temp_coeff_ta3"
    TOFFSET = "temp_coeff_offset"
    COND_CAL_DATE = "calibration_date_conductivity"
    CONDG = "cond_coeff_cg"
    CONDH = "cond_coeff_ch"
    CONDI = "cond_coeff_ci"
    CONDJ = "cond_coeff_cj"
    CPCOR = "cond_coeff_cpcor"
    CTCOR = "cond_coeff_ctcor"
    CSLOPE = "cond_coeff_cslope"
    PRES_SERIAL_NUMBER = "press_serial_number"
    PRES_RANGE = "pressure_sensor_range"
    PRES_CAL_DATE = "calibration_date_pressure"

    # Quartz
    PC1 = "press_coeff_pc1"
    PC2 = "press_coeff_pc2"
    PC3 = "press_coeff_pc3"
    PD1 = "press_coeff_pd1"
    PD2 = "press_coeff_pd2"
    PT1 = "press_coeff_pt1"
    PT2 = "press_coeff_pt2"
    PT3 = "press_coeff_pt3"
    PT4 = "press_coeff_pt4"
    PSLOPE = "press_coeff_pslope"

    # strain gauge
    PA0 = "press_coeff_pa0"
    PA1 = "press_coeff_pa1"
    PA2 = "press_coeff_pa2"
    PTCA0 = "press_coeff_ptca0"
    PTCA1 = "press_coeff_ptca1"
    PTCA2 = "press_coeff_ptca2"
    PTCB0 = "press_coeff_ptcb0"
    PTCB1 = "press_coeff_ptcb1"
    PTCB2 = "press_coeff_ptcb2"
    PTEMPA0 = "press_coeff_ptempa0"
    PTEMPA1 = "press_coeff_ptempa1"
    PTEMPA2 = "press_coeff_ptempa2"

    POFFSET = "press_coeff_poffset"
    EXT_VOLT0_OFFSET = "ext_volt0_offset"
    EXT_VOLT0_SLOPE = "ext_volt0_slope"
    EXT_VOLT1_OFFSET = "ext_volt1_offset"
    EXT_VOLT1_SLOPE = "ext_volt1_slope"
    EXT_VOLT2_OFFSET = "ext_volt2_offset"
    EXT_VOLT2_SLOPE = "ext_volt2_slope"
    EXT_VOLT3_OFFSET = "ext_volt3_offset"
    EXT_VOLT3_SLOPE = "ext_volt3_slope"
    EXT_VOLT4_OFFSET = "ext_volt4_offset"
    EXT_VOLT4_SLOPE = "ext_volt4_slope"
    EXT_VOLT5_OFFSET = "ext_volt5_offset"
    EXT_VOLT5_SLOPE = "ext_volt5_slope"
    EXT_FREQ = "ext_freq_sf"

class SBE16CalibrationParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_CALIBRATION

    @staticmethod
    def regex():
        pattern = r'SBE 16plus V'
        pattern += r'.*?'
        pattern += r'\sEXTFREQSF =\s+([\-\.\de]+)' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE16CalibrationParticle.regex(), re.DOTALL)

    def regex_multiline(self):
        """
        SBE 16plus V 2.5  SERIAL NO. 7231    26 Feb 2013 18:02:50
        temperature:  07-Nov-12
            TA0 = 1.254755e-03
            TA1 = 2.758871e-04
            TA2 = -1.368268e-06
            TA3 = 1.910795e-07
            TOFFSET = 0.000000e+00
        conductivity:  07-Nov-12
            G = -9.761799e-01
            H = 1.369994e-01
            I = -3.523860e-04
            J = 4.404252e-05
            CPCOR = -9.570000e-08
            CTCOR = 3.250000e-06
            CSLOPE = 1.000000e+00
        pressure S/N = 125270, range = 1000 psia:  02-nov-12
            PC1 = -4.642673e+03
            PC2 = -4.611640e-03
            PC3 = 8.921190e-04
            PD1 = 7.024800e-02
            PD2 = 0.000000e+00
            PT1 = 3.022595e+01
            PT2 = -1.549720e-04
            PT3 = 2.677750e-06
            PT4 = 1.705490e-09
            PSLOPE = 1.000000e+00
            POFFSET = 0.000000e+00
        volt 0: offset = -4.650526e-02, slope = 1.246381e+00
        volt 1: offset = -4.618105e-02, slope = 1.247197e+00
        volt 2: offset = -4.659790e-02, slope = 1.247601e+00
        volt 3: offset = -4.502421e-02, slope = 1.246911e+00
        volt 4: offset = -4.589158e-02, slope = 1.246346e+00
        volt 5: offset = -4.609895e-02, slope = 1.247868e+00
            EXTFREQSF = 9.999949e-01
        """
        return {
            SBE16CalibrationParticleKey.FIRMWARE_VERSION : r'SBE 16plus V (\d+\.\d+)',
            SBE16CalibrationParticleKey.SERIAL_NUMBER : r'SERIAL NO. (\d+)',
            SBE16CalibrationParticleKey.DATE_TIME : r'(\d{1,2} [\w]{3} \d{4} [\d:]+)',
            SBE16CalibrationParticleKey.TEMP_CAL_DATE : r'temperature:\s*(\d+-\w+-\d+)',
            SBE16CalibrationParticleKey.TA0 : r'\sTA0 =\s*(.*)',
            SBE16CalibrationParticleKey.TA1 : r'\sTA1 =\s*(.*)',
            SBE16CalibrationParticleKey.TA2 : r'\sTA2 =\s*(.*)',
            SBE16CalibrationParticleKey.TA3 : r'\sTA3 =\s*(.*)',
            SBE16CalibrationParticleKey.TOFFSET : r'\sTOFFSET =\s*(.*)',
            SBE16CalibrationParticleKey.COND_CAL_DATE : r'conductivity:\s+(\d+-\w+-\d+)',
            SBE16CalibrationParticleKey.CONDG : r'\sG =\s*(.*)',
            SBE16CalibrationParticleKey.CONDH : r'\sH =\s*(.*)',
            SBE16CalibrationParticleKey.CONDI : r'\sI =\s*(.*)',
            SBE16CalibrationParticleKey.CONDJ : r'\sJ =\s*(.*)',
            SBE16CalibrationParticleKey.CPCOR : r'\sCPCOR =\s*(.*)',
            SBE16CalibrationParticleKey.CTCOR : r'\sCTCOR =\s*(.*)',
            SBE16CalibrationParticleKey.CSLOPE : r'\sCSLOPE =\s*(.*)',
            SBE16CalibrationParticleKey.PRES_SERIAL_NUMBER : r'\sS\/N =\s+(\d+)',
            SBE16CalibrationParticleKey.PRES_RANGE : r'\srange =\s*(\d+)',
            SBE16CalibrationParticleKey.PRES_CAL_DATE : r'psia:\s*(\d+-\w+-\d+)',

            # strain gauge
            SBE16CalibrationParticleKey.PA0 : r'\sPA0 =\s*(.*)',
            SBE16CalibrationParticleKey.PA1 : r'\sPA1 =\s*(.*)',
            SBE16CalibrationParticleKey.PA2 : r'\sPA2 =\s*(.*)',
            SBE16CalibrationParticleKey.PTCA0 : r'PTCA0 =\s*(.*)',
            SBE16CalibrationParticleKey.PTCA1 : r'PTCA1 =\s*(.*)',
            SBE16CalibrationParticleKey.PTCA2 : r'PTCA2 =\s*(.*)',
            SBE16CalibrationParticleKey.PTCB0 : r'PTCB0 =\s*(.*)',
            SBE16CalibrationParticleKey.PTCB1 : r'PTCB1 =\s*(.*)',
            SBE16CalibrationParticleKey.PTCB2 : r'PTCB2 =\s*(.*)',
            SBE16CalibrationParticleKey.PTEMPA0 : r'PTEMPA0 = \s*(.*)',
            SBE16CalibrationParticleKey.PTEMPA1 : r'PTEMPA1 = \s*(.*)',
            SBE16CalibrationParticleKey.PTEMPA2 : r'PTEMPA2 = \s*(.*)',

            # Quartz
            SBE16CalibrationParticleKey.PC1 : r'\sPC1 =\s+(.*)',
            SBE16CalibrationParticleKey.PC2 : r'\sPC2 =\s+(.*)',
            SBE16CalibrationParticleKey.PC3 : r'\sPC3 =\s+(.*)',
            SBE16CalibrationParticleKey.PD1 : r'\sPD1 =\s+(.*)',
            SBE16CalibrationParticleKey.PD2 : r'\sPD2 =\s+(.*)',
            SBE16CalibrationParticleKey.PT1 : r'\sPT1 =\s+(.*)',
            SBE16CalibrationParticleKey.PT2 : r'\sPT2 =\s+(.*)',
            SBE16CalibrationParticleKey.PT3 : r'\sPT3 =\s+(.*)',
            SBE16CalibrationParticleKey.PT4 : r'\sPT4 =\s+(.*)',
            SBE16CalibrationParticleKey.PSLOPE : r'\sPSLOPE =\s+(.*)',
            SBE16CalibrationParticleKey.POFFSET : r'\sPOFFSET =\s+(.*)',
            SBE16CalibrationParticleKey.EXT_VOLT0_OFFSET : r'volt 0: offset =\s+(.*),',
            SBE16CalibrationParticleKey.EXT_VOLT0_SLOPE : r'volt 0: offset =\s+.*,\s+slope =\s+(.*)',
            SBE16CalibrationParticleKey.EXT_VOLT1_OFFSET : r'volt 1: offset =\s+(.*),',
            SBE16CalibrationParticleKey.EXT_VOLT1_SLOPE : r'volt 1: offset =\s+.*,\s+slope =\s+(.*)',
            SBE16CalibrationParticleKey.EXT_VOLT2_OFFSET : r'volt 2: offset =\s+(.*),',
            SBE16CalibrationParticleKey.EXT_VOLT2_SLOPE : r'volt 2: offset =\s+.*,\s+slope =\s+(.*)',
            SBE16CalibrationParticleKey.EXT_VOLT3_OFFSET : r'volt 3: offset =\s+(.*),',
            SBE16CalibrationParticleKey.EXT_VOLT3_SLOPE : r'volt 3: offset =\s+.*,\s+slope =\s+(.*)',
            SBE16CalibrationParticleKey.EXT_VOLT4_OFFSET : r'volt 4: offset =\s+(.*),',
            SBE16CalibrationParticleKey.EXT_VOLT4_SLOPE : r'volt 4: offset =\s+.*,\s+slope =\s+(.*)',
            SBE16CalibrationParticleKey.EXT_VOLT5_OFFSET : r'volt 5: offset =\s+(.*),',
            SBE16CalibrationParticleKey.EXT_VOLT5_SLOPE : r'volt 5: offset =\s+.*,\s+slope =\s+(.*)',
            SBE16CalibrationParticleKey.EXT_FREQ : r'\sEXTFREQSF =\s+(.*)',
        }

    def encoders(self):
        return {
            DEFAULT_ENCODER_KEY: float,

            SBE16CalibrationParticleKey.FIRMWARE_VERSION : str,
            SBE16CalibrationParticleKey.SERIAL_NUMBER : int,
            SBE16CalibrationParticleKey.DATE_TIME : str,
            SBE16CalibrationParticleKey.TEMP_CAL_DATE : str,
            SBE16CalibrationParticleKey.COND_CAL_DATE : str,
            SBE16CalibrationParticleKey.PRES_SERIAL_NUMBER : int,
            SBE16CalibrationParticleKey.PRES_RANGE : int,
            SBE16CalibrationParticleKey.PRES_CAL_DATE : str,
        }

    def _build_parsed_values(self):
        """
        Parse the output of the dcal command
        @throws SampleException If there is a problem with sample creation
        """
        match = SBE16CalibrationParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed status data: [%s]" %
                                  self.raw_data)

        try:
            return self._get_multiline_values()
        except ValueError as e:
            raise SampleException("ValueError while decoding status: [%s]" % e)

###############################################################################
# Seabird Electronics 16plus V2 MicroCAT Driver.
###############################################################################

class SBE16InstrumentDriver(SeaBirdInstrumentDriver):
    """
    InstrumentDriver subclass for SBE16 driver.
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    def __init__(self, evt_callback):
        """
        InstrumentDriver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        SeaBirdInstrumentDriver.__init__(self, evt_callback)

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
        self._protocol = SBE16Protocol(Prompt, NEWLINE, self._driver_event)

###############################################################################
# Seabird Electronics 37-SMP MicroCAT protocol.
###############################################################################

class SBE16Protocol(SeaBirdProtocol):
    """
    Instrument protocol class for SBE16 driver.
    Subclasses SeaBirdProtocol
    """
    def __init__(self, prompts, newline, driver_event):
        """
        SBE16Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The SBE16 newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)
        
        # Build SBE16 protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.QUIT_SESSION, self._handler_command_autosample_quit_session)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_CONFIGURATION, self._handler_command_get_configuration)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.RESET_EC, self._handler_command_reset_ec)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.TEST, self._handler_command_test)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS, self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.QUIT_SESSION, self._handler_command_autosample_quit_session)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_STATUS, self._handler_autosample_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET_CONFIGURATION, self._handler_autosample_get_configuration)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_autosample_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.ENTER, self._handler_test_enter)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.EXIT, self._handler_test_exit)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.RUN_TEST, self._handler_test_run_tests)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)


        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(Command.DS, self._build_simple_command)
        self._add_build_handler(Command.DCAL, self._build_simple_command)
        self._add_build_handler(Command.TS, self._build_simple_command)
        self._add_build_handler(Command.STARTNOW, self._build_simple_command)
        self._add_build_handler(Command.STOP, self._build_simple_command)
        self._add_build_handler(Command.TC, self._build_simple_command)
        self._add_build_handler(Command.TT, self._build_simple_command)
        self._add_build_handler(Command.TP, self._build_simple_command)
        self._add_build_handler(Command.SET, self._build_set_command)
        self._add_build_handler(Command.GETSD, self._build_simple_command)
        self._add_build_handler(Command.QS, self._build_simple_command)
        self._add_build_handler(Command.RESET_EC, self._build_simple_command)

        # Add response handlers for device commands.
        self._add_response_handler(Command.DS, self._parse_dsdc_response)
        self._add_response_handler(Command.DCAL, self._parse_dcal_response)
        self._add_response_handler(Command.SET, self._parse_set_response)
        self._add_response_handler(Command.TC, self._parse_test_response)
        self._add_response_handler(Command.TT, self._parse_test_response)
        self._add_response_handler(Command.TP, self._parse_test_response)
        self._add_response_handler(Command.GETSD, self._parse_simple_response)

        # State state machine in UNKNOWN state. 
        self._protocol_fsm.start(ProtocolState.UNKNOWN)
        
        self._chunker = StringChunker(self.sieve_function)

        self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS, ProtocolEvent.ACQUIRE_STATUS)
        self._add_scheduler_event(ScheduledJob.CONFIGURATION_DATA, ProtocolEvent.GET_CONFIGURATION)
        self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.SCHEDULED_CLOCK_SYNC)

    @staticmethod
    def sieve_function(raw_data):
        """ The method that splits samples
        """
        matchers = []
        return_list = []

        matchers.append(SBE16DataParticle.regex_compiled())
        matchers.append(SBE16StatusParticle.regex_compiled())
        matchers.append(SBE16CalibrationParticle.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
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
    
    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, next_agent_state), (ProtocolState.COMMAND or
        SBE16State.AUTOSAMPLE, next_agent_state) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the device response does not correspond to
        an expected state.
        """
        next_state = None
        next_agent_state = None

        log.debug("_handler_unknown_discover")

        logging = self._is_logging(*args, **kwargs)
        log.debug("are we logging? %s", logging)

        if(logging == None):
            raise InstrumentProtocolException('_handler_unknown_discover - unable to to determine state')

        elif(logging):
            next_state = ProtocolState.AUTOSAMPLE
            next_agent_state = ResourceAgentState.STREAMING

        else:
            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.IDLE

        log.debug("_handler_unknown_discover. result start: %s", next_state)
        return (next_state, next_agent_state)


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
        self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
            
    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_command_autosample_quit_session(self, *args, **kwargs):
        """
        put the instrument back to sleep.  This is important in autosample
        mode because this will restart sampling.
        @retval (next_state, next_agent_state)
        """
        self._do_cmd_no_resp(Command.QS, *args, **kwargs)
        return (None, None)

    def _handler_command_reset_ec(self, *args, **kwargs):
        """
        clear event counter
        @retval (next_state, next_agent_state)
        """
        self._do_cmd_no_resp(Command.RESET_EC, *args, **kwargs)
        return (None, None)

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
        startup = False

        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
        try:
            params = args[0]
            
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        try:
            startup = args[1]
        except IndexError:
            pass
        
        self._set_params(params, startup)

        return (next_state, result)

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        SeaBirdProtocol._set_params(self, *args, **kwargs)

        params = args[0]

        # Pump Mode is the only parameter that is set by the driver
        # that where the input isn't validated by the instrument.  So
        # We will do a quick range check before we start all sets
        for (key, val) in params.iteritems():
            if(key == Parameter.PUMP_MODE and val not in [0, 1, 2]):
                raise InstrumentParameterException("pump mode out of range")

        for (key, val) in params.iteritems():
            log.debug("KEY = %s VALUE = %s", key, val)

            if(key in ConfirmedParameter.list()):
                # We add a write delay here because this command has to be sent
                # twice, the write delay allows it to process the first command
                # before it receives the beginning of the second.
                response = self._do_cmd_resp(Command.SET, key, val, write_delay=0.2)
            else:
                response = self._do_cmd_resp(Command.SET, key, val, **kwargs)

        log.debug("set complete, update params")
        self._update_params()

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from SBE16.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        next_agent_state = None
        result = None

        result = self._do_cmd_resp(Command.TS, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_command_get_configuration(self, *args, **kwargs):
        """
        DCal from SBE16.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = TIMEOUT
        result = self._do_cmd_resp(Command.DCAL, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_autosample_get_configuration(self, *args, **kwargs):
        """
        DCal from SBE16.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        next_agent_state = None
        result = None

        # When in autosample this command requires two wakeups to get to the right prompt
        prompt = self._wakeup(timeout=TIMEOUT, delay=0.3)
        prompt = self._wakeup(timeout=TIMEOUT, delay=0.3)

        kwargs['timeout'] = TIMEOUT
        result = self._do_cmd_resp(Command.DCAL, *args, **kwargs)

        log.debug("quit session, restart sampling")
        self._protocol_fsm.on_event(ProtocolEvent.QUIT_SESSION)

        return (next_state, (next_agent_state, result))

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        (next_agent_state, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None

        # Assure the device is transmitting.
        if not self._param_dict.get(Parameter.TXREALTIME):
            self._do_cmd_resp(Command.SET, Parameter.TXREALTIME, True, **kwargs)

        self._start_logging(*args, **kwargs)

        next_state = ProtocolState.AUTOSAMPLE        
        next_agent_state = ResourceAgentState.STREAMING
        
        return (next_state, (next_agent_state, result))

    def _handler_command_test(self, *args, **kwargs):
        """
        Switch to test state to perform instrument tests.
        @retval (next_state, result) tuple, (ProtocolState.TEST, None).
        """

        result = None

        next_state = ProtocolState.TEST        
        next_agent_state = ResourceAgentState.TEST

        return (next_state, (next_agent_state, result))

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        result = None

        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS

        return (next_state, (next_agent_state, result))

    def _handler_command_clock_sync_clock(self, *args, **kwargs):
        """
        sync clock close to a second edge 
        @retval (next_state, result) tuple, (None, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None

        prompt = self._wakeup(timeout=TIMEOUT)

        self._sync_clock(Parameter.DATE_TIME, Prompt.COMMAND)

        return (next_state, (next_agent_state, result))


    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_clock_sync(self, *args, **kwargs):
        """
        execute a clock sync on the leading edge of a second change from
        autosample mode.  For this command we have to move the instrument
        into command mode, do the clock sync, then switch back.  If an
        exception is thrown we will try to get ourselves back into
        streaming and then raise that exception.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        result = None
        error = None

        try:
            # Switch to command mode,
            self._stop_logging(*args, **kwargs)

            # Sync the clock
            self._sync_clock(Parameter.DATE_TIME, Prompt.COMMAND, TIMEOUT, time_format="%d %b %Y %H:%M:%S")

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging(*args, **kwargs)

        if(error):
            raise error

        return (next_state, (next_agent_state, result))

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.        
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
    
    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state.
        """
        pass

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolState.COMMAND,
        (next_agent_state, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        self._stop_logging(*args, **kwargs)

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))
        
    ########################################################################
    # Common handlers.
    ########################################################################

    def _handler_command_autosample_test_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @throws InstrumentParameterException if missing or invalid parameter.
        """
        next_state = None
        result = None

        # Retrieve the required parameter, raise if not present.
        try:
            params = args[0]
           
        except IndexError:
            raise InstrumentParameterException('Get command requires a parameter list or tuple.')

        # If all params requested, retrieve config.
        if params == DriverParameter.ALL:
            result = self._param_dict.get_config()
                    
        # If not all params, confirm a list or tuple of params to retrieve.
        # Raise if not a list or tuple.
        # Retireve each key in the list, raise if any are invalid.
        else:
            if not isinstance(params, (list, tuple)):
                raise InstrumentParameterException('Get argument not a list or tuple.')
            result = {}
            for key in params:
                try:
                    val = self._param_dict.get(key)
                    result[key] = val

                except KeyError:
                    raise InstrumentParameterException(('%s is not a valid parameter.' % key))
            
        return (next_state, result)

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None
        log.debug("_handler_command_acquire_status")

        result = self._do_cmd_resp(Command.DS, timeout=TIMEOUT)

        log.debug("DS Response: %s", result)

        return (next_state, (next_agent_state, result))

    def _handler_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None

        # When in autosample this command requires two wakeups to get to the right prompt
        prompt = self._wakeup(timeout=TIMEOUT, delay=0.3)
        prompt = self._wakeup(timeout=TIMEOUT, delay=0.3)

        log.debug("_handler_autosample_acquire_status")
        result = self._do_cmd_resp(Command.DS, timeout=TIMEOUT)

        log.debug("DS Response: %s", result)

        log.debug("send the QS command to restart sampling")
        self._protocol_fsm.on_event(ProtocolEvent.QUIT_SESSION)

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Test handlers.
    ########################################################################

    def _handler_test_enter(self, *args, **kwargs):
        """
        Enter test state. Setup the secondary call to run the tests.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.        
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        
        # Forward th test event again to run the test handler and
        # switch back to command mode afterward.
        Timer(1, lambda: self._protocol_fsm.on_event(ProtocolEvent.RUN_TEST)).start()
    
    def _handler_test_exit(self, *args, **kwargs):
        """
        Exit test state.
        """
        pass

    def _handler_test_run_tests(self, *args, **kwargs):
        """
        Run test routines and validate results.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        tc_pass = False
        tt_pass = False
        #tp_pass = False
        tc_result = None
        tt_result = None
        #tp_result = None

        test_result = {}

        try:
            tc_pass, tc_result = self._do_cmd_resp(Command.TC, timeout=200)
            tt_pass, tt_result = self._do_cmd_resp(Command.TT, timeout=200)
            tp_pass, tp_result = self._do_cmd_resp(Command.TP, timeout=200)
        
        except Exception as e:
            test_result['exception'] = e
            test_result['message'] = 'Error running instrument tests.'
        
        finally:
            test_result['cond_test'] = 'Passed' if tc_pass else 'Failed'
            test_result['cond_data'] = tc_result
            test_result['temp_test'] = 'Passed' if tt_pass else 'Failed'
            test_result['temp_data'] = tt_result
            test_result['pres_test'] = 'Passed' if tp_pass else 'Failed'
            test_result['pres_data'] = tp_result
            test_result['success'] = 'Passed' if (tc_pass and tt_pass and tp_pass) else 'Failed'
            test_result['success'] = 'Passed' if (tc_pass and tt_pass) else 'Failed'
            test_result['desc'] = 'SBE16Plus-V2 self-test result'
            test_result['cmd'] = DriverEvent.TEST
            
        self._driver_event(DriverAsyncEvent.RESULT, test_result)
        self._driver_event(DriverAsyncEvent.AGENT_EVENT, ResourceAgentEvent.DONE)

        next_state = ProtocolState.COMMAND
        return (next_state, result)

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

    ########################################################################
    # Private helpers.
    ########################################################################

    def _is_logging(self, *args, **kwargs):
        """
        Wake up the instrument and inspect the prompt to determine if we
        are in streaming
        @param: timeout - Command timeout
        @return: True - instrument logging, False - not logging,
                 None - unknown logging state
        @raise: InstrumentProtocolException if we can't identify the prompt
        """
        self._update_params(*args, **kwargs)
        pd = self._param_dict.get_config()
        return pd.get(Parameter.LOGGING)

    def _start_logging(self, *args, **kwargs):
        """
        Command the instrument to start logging
        @param timeout: how long to wait for a prompt
        @return: True if successful
        @raise: InstrumentProtocolException if failed to start logging
        """
        log.debug("Start Logging!")
        if(self._is_logging()):
            return True

        self._do_cmd_no_resp(Command.STARTNOW, *args, **kwargs)
        time.sleep(2)

        if not self._is_logging(20):
            raise InstrumentProtocolException("failed to start logging")

        return True

    def _stop_logging(self, *args, **kwargs):
        """
        Command the instrument to stop logging
        @param timeout: how long to wait for a prompt
        @return: True if successful
        @raise: InstrumentTimeoutException if prompt isn't seen
        @raise: InstrumentProtocolException failed to stop logging
        """
        log.debug("Stop Logging!")

        prompt = self._wakeup(timeout=TIMEOUT, delay=0.3)
        prompt = self._wakeup(timeout=TIMEOUT, delay=0.3)

        # Issue the stop command.
        if(self.get_current_state() == ProtocolState.AUTOSAMPLE):
            log.debug("sending stop logging command")
            kwargs['timeout'] = TIMEOUT
            self._do_cmd_resp(Command.STOP, *args, **kwargs)
        else:
            log.debug("Instrument not logging, current state %s", self.get_current_state())

        if self._is_logging(*args, **kwargs):
            raise InstrumentProtocolException("failed to stop logging")

        return True


    def _get_utc_time_at_second_edge(self):
                
        while datetime.datetime.utcnow().microsecond != 0:
            pass

        gmTime = time.gmtime(time.mktime(time.localtime()))
        return time.strftime("%d %b %Y %H:%M:%S", gmTime)
        
    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the SBE16 device.
        """
        self._connection.send(NEWLINE)
                
    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Wake the device then issue
        display status and display calibration commands. The parameter
        dict will match line output and udpate itself.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        prompt = self._wakeup(timeout=TIMEOUT, delay=0.3)

        # For some reason when in streaming we require a second wakeup
        prompt = self._wakeup(timeout=TIMEOUT, delay=0.3)

        # Get old param dict config.
        old_config = self._param_dict.get_config()
        
        # Issue display commands and parse results.
        log.debug("device status from _update_params")
        self._do_cmd_resp(Command.DS, timeout=TIMEOUT)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()

        ###
        # The 16plus V2 responds only to GetCD, GetSD, GetCC, GetEC,
        # ResetEC, GetHD, DS, DCal, TS, SL, SLT, GetLastSamples:x, QS, and
        # Stop while sampling autonomously. If you wake the 16plus V2 while it is
        # sampling autonomously (for example, to send DS to check on progress), it
        # temporarily stops sampling. Autonomous sampling resumes when it
        ###
        if(new_config.get(Parameter.LOGGING)):
            self._do_cmd_no_resp(Command.QS, timeout=TIMEOUT)

        # We ignore the data time parameter diffs
        new_config[Parameter.DATE_TIME] = old_config.get(Parameter.DATE_TIME)

        if new_config != old_config and self._protocol_fsm.get_current_state() != ProtocolState.UNKNOWN:
            log.debug("parameters updated, sending event")
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        else:
            log.debug("no configuration change.")


    def _build_simple_command(self, cmd):
        """
        Build handler for basic SBE16 commands.
        @param cmd the simple sbe16 command to format.
        @retval The command to be sent to the device.
        """
        return "%s%s" % (cmd, NEWLINE)
    
    def _build_set_command(self, cmd, param, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        try:
            str_val = self._param_dict.format(param, val)
            
            if param == 'INTERVAL':
                param = 'sampleinterval'

            set_cmd = '%s=%s' % (param, str_val)
            set_cmd = set_cmd + NEWLINE

            # Some set commands need to be sent twice to confirm
            if(param in ConfirmedParameter.list()):
                set_cmd = set_cmd + set_cmd

        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)
            
        return set_cmd

    def _find_error(self, response):
        """
        Find an error xml message in a response
        @param response command response string.
        @return tuple with type and message, None otherwise
        """
        match = re.search(ERROR_REGEX, response)
        if(match):
            return (match.group(1), match.group(2))

        return None

    def _parse_simple_response(self, response, prompt):
        """
        Parse handler for basic commands
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentParameterException('command failure: type="%s" msg="%s"' % (error[0], error[1]))

        return response

    def _parse_set_response(self, response, prompt):
        """
        Parse handler for set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("Set command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentParameterException('Set command failure: type="%s" msg="%s"' % (error[0], error[1]))

        if prompt not in [Prompt.EXECUTED, Prompt.COMMAND]:
            log.error("Set command encountered error; instrument returned: %s", response)
            raise InstrumentProtocolException('Set command not recognized: %s' % response)

    def _parse_dsdc_response(self, response, prompt):
        """
        Parse handler for dsdc commands.
        @param response command response string.
        @param prompt prompt following command response.        
        @throws InstrumentProtocolException if dsdc command misunderstood.
        """
        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]: 
            raise InstrumentProtocolException('dsdc command not recognized: %s.' % response)

        for line in response.split(NEWLINE):
            self._param_dict.update(line)

        return response

    def _parse_dcal_response(self, response, prompt):
        """
        Parse handler for dsdc commands.
        @param response command response string.
        @param prompt prompt following command response.        
        @throws InstrumentProtocolException if dsdc command misunderstood.
        """
        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            raise InstrumentProtocolException('dcal command not recognized: %s.' % response)
            
        for line in response.split(NEWLINE):
            self._param_dict.update(line)

        return response
        
    def _parse_test_response(self, response, prompt):
        """
        Do minimal checking of test outputs.
        @param response command response string.
        @param promnpt prompt following command response.
        @retval tuple of pass/fail boolean followed by response
        """
        
        success = False
        lines = response.split()
        if len(lines)>2:
            data = lines[1:-1]
            bad_count = 0
            for item in data:
                try:
                    float(item)
                    
                except ValueError:
                    bad_count += 1
            
            if bad_count == 0:
                success = True
        
        return (success, response)        
                
    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes. 
        """
        if not (self._extract_sample(SBE16DataParticle, SBE16DataParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE16StatusParticle, SBE16StatusParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE16CalibrationParticle, SBE16CalibrationParticle.regex_compiled(), chunk, timestamp)):
            raise InstrumentProtocolException("Unhandled chunk")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with SBE16 parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        self._param_dict.add(Parameter.DATE_TIME,
                             r'SBE 16plus V ([\w.]+) +SERIAL NO. (\d+) +(\d{2} [a-zA-Z]{3,4} \d{4} +[\d:]+)',
                             lambda match : string.upper(match.group(3)),
                             self._string_to_numeric_date_time_string,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.ECHO,
                             r'echo characters = (yes|no)',
                             lambda match : True if match.group(1)=='yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.OUTPUT_EXEC_TAG,
                             r'.',
                             lambda match : True,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.TXREALTIME,
                             r'transmit real-time = (yes|no)',
                             lambda match : True if match.group(1)=='yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PUMP_MODE,
                             r'pump = (run pump during sample|run pump for 0.5 sec|no pump)',
                             self._pump_mode_to_int,
                             str,
                             startup_param = True,
                             direct_access = True,
                             default_value = 2)
        self._param_dict.add(Parameter.NCYCLES,
                             r'number of measurements per sample = (\d+)',
                             lambda match : int(match.group(1)),
                             str,
                             startup_param = True,
                             direct_access = False,
                             default_value = 4)
        self._param_dict.add(Parameter.INTERVAL,
                             r'sample interval = (\d+)',
                             lambda match : int(match.group(1)),
                             str,
                             startup_param = True,
                             direct_access = False,
                             default_value = 10)
        self._param_dict.add(Parameter.BIOWIPER,
                             r'.',
                             lambda match : False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PTYPE,
                             r'pressure sensor = ([\w\s]+),',
                             self._pressure_sensor_to_int,
                             self._int_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = 1,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.VOLT0,
                             r'Ext Volt 0 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.VOLT1,
                             r'Ext Volt 1 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.VOLT2,
                             r'Ext Volt 2 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.VOLT3,
                             r'Ext Volt 3 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.VOLT4,
                             r'Ext Volt 4 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.VOLT5,
                             r'Ext Volt 5 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.DELAY_BEFORE_SAMPLE,
                             r'delay before sampling = (\d+\.\d+)',
                             lambda match : float(match.group(1)),
                             self._float_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = 0.0,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.DELAY_AFTER_SAMPLE,
                             r'delay after sampling = (\d\.\d)',
                             lambda match : float(match.group(1)),
                             str,
                             startup_param = True,
                             direct_access = True,
                             default_value = 0.0,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.SBE63,
                             r'SBE\s?63 = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.SBE38,
                             r'SBE 38 = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.SBE50,
                             r'SBE 50 = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.WETLABS,
                             r'WETLABS = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.GTD,
                             r'Gas Tension Device = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.OPTODE,
                             r'OPTODE = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.SYNCMODE,
                             r'serial sync mode (dis|en)abled',
                             lambda match : True if match.group(1) == 'en' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.SYNCWAIT,
                             r'wait time after sampling = (\d) seconds',
                             lambda match : int(match.group(1)),
                             str,
                             # Not a startup parameter because syncmode is read only false.
                             # This parameter is not needed.
                             startup_param = False,
                             direct_access = False,
                             default_value = 0,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.OUTPUT_FORMAT,
                             r'output format = (raw HEX)',
                             self._output_format_string_2_int,
                             int,
                             startup_param = True,
                             direct_access = True,
                             default_value = 0,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.LOGGING,
                             r'status = (not )?logging',
                             lambda match : False if (match.group(1)) else True,
                             self._true_false_to_string,
                             visibility=ParameterDictVisibility.READ_ONLY)


    ########################################################################
    # Static helpers to format set commands.
    ########################################################################

    @staticmethod
    def _pressure_sensor_to_int(match):
        """
        map a pressure sensor string into an int representation
        @param v: regex match
        @return: mode 1, 2, 3 or None for no match
        """
        v = match.group(1)

        log.debug("get pressure type from: %s", v)
        if(v == "strain gauge"):
            return 1
        elif(v == "quartz without temp comp"):
            return 2
        elif(v == "quartz with temp comp"):
            return 3
        else:
            return None

    @staticmethod
    def _pump_mode_to_int(match):
        """
        map a pump mode string into an int representation
        @param v: regex match
        @return: mode 0, 1, 2 or None for no match
        """
        v = match.group(1)

        log.debug("get pump mode from: %s", v)
        if(v == "no pump"):
            return 0
        elif(v == "run pump for 0.5 sec"):
            return 1
        elif(v == "run pump during sample"):
            return 2
        else:
            return None

    @staticmethod
    def _true_false_to_string(v):
        """
        Write a boolean value to string formatted for sbe16 set operations.
        @param v a boolean value.
        @retval A yes/no string formatted for sbe16 set operations.
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
        Write an int value to string formatted for sbe16 set operations.
        @param v An int val.
        @retval an int string formatted for sbe16 set operations.
        @throws InstrumentParameterException if value not an int.
        """
        
        if not isinstance(v,int):
            raise InstrumentParameterException('Value %s is not an int.' % str(v))
        else:
            return '%i' % v

    @staticmethod
    def _float_to_string(v):
        """
        Write a float value to string formatted for sbe16 set operations.
        @param v A float val.
        @retval a float string formatted for sbe16 set operations.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v,float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            return '%e' % v

    @staticmethod
    def _date_to_string(v):
        """
        Write a date tuple to string formatted for sbe16 set operations.
        @param v a date tuple: (day,month,year).
        @retval A date string formatted for sbe16 set operations.
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
    def _string_to_date(datestr,fmt):
        """
        Extract a date tuple from an sbe16 date string.
        @param str a string containing date information in sbe16 format.
        @retval a date tuple.
        @throws InstrumentParameterException if datestr cannot be formatted to
        a date.
        """
        if not isinstance(datestr,str):
            raise InstrumentParameterException('Value %s is not a string.' % str(datestr))
        try:
            date_time = time.strptime(datestr,fmt)
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

    @staticmethod
    def _output_format_int_2_string(format_int):
        """
        Convert an output format from an int to a string
        @param format_int sbe output format as int
        @retval string representation of output format
        @raise InstrumentParameterException if int out of range.
        """
        if(format_int == 0):
            return "raw HEX"
        elif(format_int == 1):
            return "converted HEX"
        elif(format_int == 2):
            return "raw decimal"
        elif(format_int == 3):
            return "converted decimal"
        # Uncomment once we figure out the thread locking issue
        #elif(format_int == 5):
        #    return "converted XML UVIC"
        else:
            raise InstrumentParameterException("output format out of range: %s" % format_int)

    @staticmethod
    def _output_format_string_2_int(format_string):
        """
        Convert an output format from an string to an int
        @param format_string sbe output format as string or regex match
        @retval int representation of output format
        @raise InstrumentParameterException if format unknown
        """
        if(not isinstance(format_string, str)):
            format_string = format_string.group(1)

        if(format_string.lower() ==  "raw hex"):
            return 0
        elif(format_string.lower() == "converted hex"):
            return 1
        elif(format_string.lower() == "raw decimal"):
            return 2
        elif(format_string.lower() == "converted decimal"):
            return 3
        else:
            raise InstrumentParameterException("output format unknown: %s" % format_string)
