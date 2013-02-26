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

class ScheduledJob(BaseEnum):
    ACQUIRE_STATUS = 'acquire_status'
    CONFIGURATION_DATA = "configuration_data"
    STATUS_DATA = "status_data"
    EVENT_COUNTER_DATA = "event_counter"
    HARDWARE_DATA = "hardware_data"
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

class ProtocolState(BaseEnum):
    """
    Protocol states for SBE16. Cherry picked from DriverProtocolState
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    TEST = DriverProtocolState.TEST
    CALIBRATE = DriverProtocolState.CALIBRATE
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
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    TEST = DriverEvent.TEST
    RUN_TEST = DriverEvent.RUN_TEST
    CALIBRATE = DriverEvent.CALIBRATE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    FORCE_STATE = DriverEvent.FORCE_STATE
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS

class Capability(BaseEnum):
    """
    Capabilities that are exposed to the user (subset of above)
    NOTE: I have GET and SET here because these do not get exported
    to the run_instrument (or any other UI) at this point, and I 
    need their functionality.
    """
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    TEST = DriverEvent.TEST
    DISCOVER = DriverEvent.DISCOVER


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
    PUMP_MODE = "pump_mode"
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
    DUALGTD = "DualGTD"
    OPTODE = "OPTODE"
    SYNCMODE = "SyncMode"
    SYNCWAIT = "SyncWait"
    OUTPUT_FORMAT = "OutputFormat"

    # Remove?
    SAMPLENUM = 'SampleNumber'
    OUTPUTSAL = 'OUTPUTSAL'
    OUTPUTSV = 'OUTPUTSV'
    NAVG = 'NAVG' # NCycles
# Device prompts.
class Prompt(BaseEnum):
    """
    SBE16 io prompts.
    """
    COMMAND = 'S>'
    BAD_COMMAND = '?cmd S>'
    #AUTOSAMPLE = 'S>\r\n'
    AUTOSAMPLE = 'S>'
    EXECUTED = '<Executed/>'

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    CTD_PARSED = 'ctdbp_cdef_parsed'
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
            temperature = SeaBirdProtocol.hex2value(match.group(1))
            conductivity = SeaBirdProtocol.hex2value(match.group(2))
            pressure = SeaBirdProtocol.hex2value(match.group(3))
            pressure_temp = SeaBirdProtocol.hex2value(match.group(4))
            elapse_time = SeaBirdProtocol.hex2value(match.group(5))
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
            SBE16StatusParticleKey.FREE : int,
            SBE16StatusParticleKey.MEASUREMENTS_PER_SAMPLE : int,
            SBE16StatusParticleKey.DELAY_BEFORE_SAMPLING : float,
            SBE16StatusParticleKey.DELAY_AFTER_SAMPLING : float,
            SBE16StatusParticleKey.TX_REAL_TIME : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.BATTERY_CUTOFF : float,
            SBE16StatusParticleKey.RANGE : float,
            SBE16StatusParticleKey.SBE38 : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.SBE50 : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.WETLABS : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.OPTODE : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.GAS_TENSION_DEVICE : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.EXT_VOLT_0 : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.EXT_VOLT_1 : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.EXT_VOLT_2 : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.EXT_VOLT_3 : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.EXT_VOLT_4 : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.EXT_VOLT_5 : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.ECHO_CHARACTERS : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.OUTPUT_SALINITY : SeaBirdProtocol.yesno2bool,
            SBE16StatusParticleKey.OUTPUT_SOUND_VELOCITY : SeaBirdProtocol.yesno2bool,
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
            SBE16StatusParticleKey.VBATT : r'vbatt = (\d+.\d+),',
            SBE16StatusParticleKey.VLITH : r'vlith *= *(\d+.\d+),',
            SBE16StatusParticleKey.IOPER : r'ioper =\s+(\d+.\d+) [a-zA-Z]+',
            SBE16StatusParticleKey.IPUMP : r'ipump = (\d+.\d+) [a-zA-Z]+,',
            SBE16StatusParticleKey.STATUS : r'status = (\w+ +\w+)',
            SBE16StatusParticleKey.SAMPLES : r'samples = (\d+)',
            SBE16StatusParticleKey.FREE : r'free = (\d+)',
            SBE16StatusParticleKey.SAMPLE_INTERVAL : r'sample interval = (\d+ *\w+),',
            SBE16StatusParticleKey.MEASUREMENTS_PER_SAMPLE :  r'number of measurements per sample = (\d+)',
            SBE16StatusParticleKey.PUMP_MODE :  r'^pump = ([ \w]+)',
            SBE16StatusParticleKey.DELAY_BEFORE_SAMPLING : r'delay before sampling = (\d+.\d+) \w+',
            SBE16StatusParticleKey.DELAY_AFTER_SAMPLING : r'delay after sampling = (\d+.\d+) \w+',
            SBE16StatusParticleKey.TX_REAL_TIME : r'transmit real-time = (\w+) *',
            SBE16StatusParticleKey.BATTERY_CUTOFF : r'battery cutoff =\s+(\d+.\d+) \w+',
            SBE16StatusParticleKey.PRESSURE_SENSOR : r'pressure sensor = ([\s\w])*,',
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
            SBE16StatusParticleKey.OUTPUT_FORMAT : r'output format = (\w+)',
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
            log.debug("building it")
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

class SBE16CalibrationParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_CALIBRATION

    @staticmethod
    def regex():
        pattern = r'XXXXXXXXXX' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE16CalibrationParticle.regex())

    def _build_parsed_values(self):
        result = []
        return result

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
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.FORCE_STATE, self._handler_unknown_force_state) 
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.TEST, self._handler_command_test)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_STATUS, self._handler_command_autosample_acquire_status)
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
        # DHE dcal replaces dc
        self._add_build_handler(Command.DCAL, self._build_simple_command)
        self._add_build_handler(Command.TS, self._build_simple_command)
        self._add_build_handler(Command.STARTNOW, self._build_simple_command)
        self._add_build_handler(Command.STOP, self._build_simple_command)
        self._add_build_handler(Command.TC, self._build_simple_command)
        self._add_build_handler(Command.TT, self._build_simple_command)
        self._add_build_handler(Command.TP, self._build_simple_command)
        self._add_build_handler(Command.SET, self._build_set_command)

        # Add response handlers for device commands.
        self._add_response_handler(Command.DS, self._parse_dsdc_response)
        self._add_response_handler(Command.DCAL, self._parse_dcal_response)
        self._add_response_handler(Command.SET, self._parse_set_response)
        self._add_response_handler(Command.TC, self._parse_test_response)
        self._add_response_handler(Command.TT, self._parse_test_response)
        self._add_response_handler(Command.TP, self._parse_test_response)

        # State state machine in UNKNOWN state. 
        self._protocol_fsm.start(ProtocolState.UNKNOWN)
        
        self._chunker = StringChunker(self.sieve_function)
        

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
        
        current_state = self._protocol_fsm.get_current_state()
        
        next_state = None
        next_agent_state = None

        timeout = kwargs.get('timeout', TIMEOUT)
        prompt = self._wakeup(timeout)
        prompt = self._wakeup(timeout)

        """
        get the configuration parameters; one of the params is the logging 
        parameter, which tells us if we're in AUTOSAMPLE or not.
        """
        self._do_cmd_resp(Command.DS,timeout=timeout)
        self._do_cmd_resp(Command.DCAL,timeout=timeout)
        config = self._param_dict.get_config()

        logging_state = config[Parameter.LOGGING]
        log.debug("SBE16plus_v2 logging state is: %s", str(logging_state))
        if logging_state == True:
            next_state = ProtocolState.AUTOSAMPLE
            next_agent_state = ResourceAgentState.STREAMING
        elif logging_state == False:
            """
            Set the time here; might want to move this to somewhere else
            """
            str_utc_time = get_timestamp_delayed("%d %b %Y %H:%M:%S")
            self._do_cmd_resp(Command.SET, Parameter.DATE_TIME,
                      str_utc_time, **kwargs)
            log.info("SBE16plus_v2 time set to UTC: %s", str_utc_time) 

            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.IDLE
        else:
            errorString = 'Unknown state based on value of configuration parameter LOGGING: ' + str(logging_state)
            log.error(errorString)
            raise InstrumentStateException(errorString)
            
        return (next_state, next_agent_state)

    def _handler_unknown_force_state(self, *args, **kwargs):
        """
        Force driver into a given state for the purposes of unit testing 
        @param state=desired_state Required desired state to transition to.
        @raises InstrumentParameterException if no state parameter.
        """

        state = kwargs.get('state', None)  # via kwargs
        if state is None:
            raise InstrumentParameterException('Missing state parameter.')

        next_state = state
        result = state
        
        return (next_state, result)


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
            
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')
        
        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        else:
            
            for (key, val) in params.iteritems():
                result = self._do_cmd_resp(Command.SET, key, val, **kwargs)
            self._update_params()
            
        return (next_state, result)

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
        
        # Issue start command and switch to autosample if successful.
        self._do_cmd_no_resp(Command.STARTNOW, *args, **kwargs)
                
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

        timeout = kwargs.get('timeout', TIMEOUT)
        prompt = self._wakeup(timeout=timeout)
        
        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            error_msg = "Error synchronizing clock; instrument returned: " + prompt
            raise InstrumentProtocolException(error_msg)

        str_utc_time = get_timestamp_delayed("%d %b %Y %H:%M:%S")
        # Using base class version
        #str_utc_time = self._get_utc_time_at_second_edge()
        self._do_cmd_resp(Command.SET, Parameter.DATE_TIME,
                  str_utc_time, **kwargs)
        log.info("SBE16plus_v2 time set to UTC: %s", str_utc_time) 

        return (next_state, (next_agent_state, result))


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

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', TIMEOUT)
        tries = kwargs.get('tries',5)
        notries = 0
        try:
            # DHE: there should really be a tuple of expected prompts
            #self._wakeup_until(timeout, Prompt.AUTOSAMPLE)
            self._wakeup_until(timeout, Prompt.EXECUTED)
        
        except InstrumentTimeoutException:
            notries = notries + 1
            if notries >= tries:
                raise

        # Issue the stop command.
        self._do_cmd_resp(Command.STOP, *args, **kwargs)        
        
        # Prompt device until command prompt is seen.
        # DHE: there should really be a tuple of expected prompts
        #self._wakeup_until(timeout, Prompt.COMMAND)
        self._wakeup_until(timeout, Prompt.EXECUTED)
        
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

    def _handler_command_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 30
        result = self._do_cmd_no_resp('ds', *args, **kwargs)

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
        
        # Forward the test event again to run the test handler and
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

        # Get old param dict config.
        old_config = self._param_dict.get_config()
        
        # Issue display commands and parse results.
        timeout = kwargs.get('timeout', TIMEOUT)
        self._do_cmd_resp(Command.DS, timeout=timeout)
        self._do_cmd_resp(Command.DCAL, timeout=timeout)
        
        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        
    def _build_simple_command(self, cmd):
        """
        Build handler for basic SBE16 commands.
        @param cmd the simple sbe16 command to format.
        @retval The command to be sent to the device.
        """
        return cmd+NEWLINE
    
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
            if 'sample interval' in line:
                for sline in line.split(','):
                    self._param_dict.update(sline.lstrip())
            elif 'output salinity' in line:
                for sline in line.split(','):
                    self._param_dict.update(sline.lstrip())
            else: 
                self._param_dict.update(line)
            
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
        if(self._extract_sample(SBE16DataParticle, SBE16DataParticle.regex_compiled(), chunk, timestamp)):
            pass
        elif(self._extract_sample(SBE16StatusParticle, SBE16StatusParticle.regex_compiled(), chunk, timestamp)):
            pass
        #elif(self._extract_sample(SBE16CalibrationParticle, SBE16CalibrationParticle.regex_compiled(), chunk, timestamp)):
        #    pass
        else:
            raise InstrumentProtocolException("Unhandled chunk")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with SBE16 parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.        
        self._param_dict.add(Parameter.OUTPUTSAL,
                             r'output salinity = (no)?',
                             lambda match : False if match.group(1) else True,
                             self._true_false_to_string,
                             startup_param = True)
        self._param_dict.add(Parameter.OUTPUTSV,
                             r'output sound velocity = (no)?',
                             lambda match : False if match.group(1) else True,
                             self._true_false_to_string)
        self._param_dict.add(Parameter.NAVG,
                             r'number of measurements per sample = (\d+)',
                             lambda match : int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.SAMPLENUM,
                             r'samples = (\d+), free = \d+',
                             lambda match : int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.INTERVAL,
                             r'sample interval = (\d+) seconds',
                             lambda match : int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(Parameter.TXREALTIME,
                             r'transmit real-time = (yes|no)',
                             lambda match : True if match.group(1)=='yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True)
        self._param_dict.add(Parameter.DATE_TIME,
                             r'SBE 16plus V ([\w.]+) +SERIAL NO. (\d+) +(\d{2} [a-zA-Z]{3,4} \d{4} +[\d:]+)', 
                             lambda match : string.upper(match.group(3)),
                             self._string_to_numeric_date_time_string,
                             startup_param = True,
                             direct_access = True)
        self._param_dict.add(Parameter.ECHO,
                             r'echo characters = (yes|no)',
                             lambda match : True if match.group(1)=='yes' else False,
                             self._true_false_to_string,
                             startup_param = True,
                             direct_access = True)
#        self._param_dict.add(Parameter.PUMP_MODE,
#                             r'pump = run pump during sample',
#                             lambda match : True if match.group(1)=='yes' else False,
#                             self._true_false_to_string,
#                             startup_param = True,
#                             direct_access = True)
        self._param_dict.add(Parameter.LOGGING,
                             r'status = (not )?logging',
                             lambda match : False if (match.group(1)) else True,
                             self._true_false_to_string)
                             

    ########################################################################
    # Static helpers to format set commands.
    ########################################################################

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
    
