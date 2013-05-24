"""
@package mi.instrument.seabird.sbe54tps.ooicore.driver
@file /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe54tps/ooicore/driver.py
@author Roger Unwin
@brief Driver for the ooicore
Release notes:

10.180.80.170:2101 Instrument
10.180.80.170:2102 Digi
Done
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import string
import re
import time
import ntplib
from mi.core.log import get_logger ; log = get_logger()

from mi.core.util import dict_equal
from mi.core.common import BaseEnum
from mi.core.time import get_timestamp_delayed
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.driver_dict import DriverDictKey

from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterExpirationException

from mi.core.instrument.data_particle import DataParticle, DataParticleKey, CommonDataParticleType
from mi.core.instrument.chunker import StringChunker
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

from mi.instrument.seabird.driver import SeaBirdInstrumentDriver
from mi.instrument.seabird.driver import SeaBirdProtocol
from mi.instrument.seabird.driver import NEWLINE
from mi.instrument.seabird.driver import TIMEOUT

class ScheduledJob(BaseEnum):
    ACQUIRE_STATUS = 'acquire_status'
    CONFIGURATION_DATA = "configuration_data"
    STATUS_DATA = "status_data"
    EVENT_COUNTER_DATA = "event_counter"
    HARDWARE_DATA = "hardware_data"
    CLOCK_SYNC = 'clock_sync'

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    PREST_REAL_TIME = 'prest_real_time'
    PREST_REFERENCE_OSCILLATOR = 'prest_reference_oscillator'
    PREST_CONFIGURATION_DATA = 'prest_configuration_data'
    PREST_DEVICE_STATUS = 'prest_device_status'
    PREST_EVENT_COUNTER = 'prest_event_counter'
    PREST_HARDWARE_DATA = 'prest_hardware_data'
    
# Device specific parameters.
class InstrumentCmds(BaseEnum):
    """
    Instrument Commands
    These are the commands that according to the science profile must be supported.
    """
    # Artificial Constructed Commands for Driver
    SET = "set"  # need to bring over _build_set_command/_parse_set_response

    # Status
    GET_CONFIGURATION_DATA = "GetCD"
    GET_STATUS_DATA = "GetSD"
    GET_EVENT_COUNTER_DATA = "GetEC"
    GET_HARDWARE_DATA = "GetHD"

    # Setup - General
    SET_SAMPLE_PERIOD = "SetSamplePeriod"
    SET_TIME = "SetTime"
    SET_BATTERY_TYPE = "SetBatteryType"

    # Setup Data Output
    SET_ENABLE_ALERTS = "SetEnableAlerts"

    # Sampling
    INIT_LOGGING = "InitLogging"
    START_LOGGING = "Start"
    STOP_LOGGING = "Stop"
    SAMPLE_REFERENCE_OSCILLATOR = "SampleRefOsc"

    # Diagnostic
    RESET_EC = "ResetEC"
    TEST_EEPROM = "TestEeprom"

class ProtocolState(BaseEnum):
    """
    Protocol states
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    RECOVER_AUTOSAMPLE = 'PROTOCOL_EVENT_RECOVER_AUTOSAMPLE'
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    SAMPLE_REFERENCE_OSCILLATOR = 'PROTOCOL_EVENT_SAMPLE_REFERENCE_OSCILLATOR'
    TEST_EEPROM = 'PROTOCOL_EVENT_TEST_EEPROM'
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    PING_DRIVER = DriverEvent.PING_DRIVER
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    SCHEDULED_CLOCK_SYNC = 'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC'
    GET_CONFIGURATION_DATA = 'PROTOCOL_EVENT_GET_CONFIGURATION'
    GET_STATUS_DATA = 'PROTOCOL_EVENT_GET_STATUS'
    GET_EVENT_COUNTER = 'PROTOCOL_EVENT_GET_EVENT_COUNTER'
    GET_HARDWARE_DATA = 'PROTOCOL_EVENT_GET_HARDWARE'

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
    ACQUIRE_STATUS  = ProtocolEvent.ACQUIRE_STATUS
    SAMPLE_REFERENCE_OSCILLATOR = ProtocolEvent.SAMPLE_REFERENCE_OSCILLATOR
    TEST_EEPROM = ProtocolEvent.TEST_EEPROM
    GET_CONFIGURATION_DATA = ProtocolEvent.GET_CONFIGURATION_DATA
    GET_STATUS_DATA = ProtocolEvent.GET_STATUS_DATA
    GET_EVENT_COUNTER = ProtocolEvent.GET_EVENT_COUNTER
    GET_HARDWARE_DATA = ProtocolEvent.GET_HARDWARE_DATA

# Device specific parameters.
class Parameter(DriverParameter):
    TIME = "time" # str
    SAMPLE_PERIOD = "sampleperiod" # int
    ENABLE_ALERTS = "enablealerts" # bool
    BATTERY_TYPE = "batterytype" # int

# Device prompts.
class Prompt(BaseEnum):
    COMMAND = "<Executed/>\r\nS>"
    AUTOSAMPLE = "<Executed/>\r\n"
    BAD_COMMAND_AUTOSAMPLE = "<Error.*?\r\n<Executed/>\r\n" # REGEX ALERT
    BAD_COMMAND = "<Error.*?\r\n<Executed/>\r\nS>" # REGEX ALERT


######################### PARTICLES #############################

STATUS_DATA_REGEX = r"(<StatusData DeviceType='.*?</StatusData>)"
STATUS_DATA_REGEX_MATCHER = re.compile(STATUS_DATA_REGEX, re.DOTALL)

CONFIGURATION_DATA_REGEX = r"(<ConfigurationData DeviceType=.*?</ConfigurationData>)"
CONFIGURATION_DATA_REGEX_MATCHER = re.compile(CONFIGURATION_DATA_REGEX, re.DOTALL)

EVENT_COUNTER_DATA_REGEX = r"(<EventSummary numEvents='.*?</EventList>)"
EVENT_COUNTER_DATA_REGEX_MATCHER = re.compile(EVENT_COUNTER_DATA_REGEX, re.DOTALL)

HARDWARE_DATA_REGEX = r"(<HardwareData DeviceType='.*?</HardwareData>)"
HARDWARE_DATA_REGEX_MATCHER = re.compile(HARDWARE_DATA_REGEX, re.DOTALL)

SAMPLE_DATA_REGEX = r"<Sample Num='[0-9]+' Type='Pressure'>.*?</Sample>"
SAMPLE_DATA_REGEX_MATCHER = re.compile(SAMPLE_DATA_REGEX, re.DOTALL)

SAMPLE_REF_OSC_REGEX = r"<SetTimeout>.*?</Sample>"
SAMPLE_REF_OSC_MATCHER = re.compile(SAMPLE_REF_OSC_REGEX, re.DOTALL)

ENGINEERING_DATA_REGEX = "<MainSupplyVoltage>([.\d]+)</MainSupplyVoltage>"
ENGINEERING_DATA_MATCHER = re.compile(SAMPLE_REF_OSC_REGEX, re.DOTALL)

class SBE54tpsStatusDataParticleKey(BaseEnum):
    DEVICE_TYPE = "device_type"
    SERIAL_NUMBER = "serial_number"
    TIME = "date_time_str"
    EVENT_COUNT = "event_count"
    MAIN_SUPPLY_VOLTAGE = "battery_voltage_main"
    NUMBER_OF_SAMPLES = "sample_number"
    BYTES_USED = "bytes_used"
    BYTES_FREE = "bytes_free"

class SBE54tpsStatusDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.PREST_DEVICE_STATUS

    LINE1 = r"<StatusData DeviceType='([^']+)' SerialNumber='(\d+)'>"
    LINE2 = r"<DateTime>([^<]+)</DateTime>"
    LINE3 = r"<EventSummary numEvents='(\d+)'/>"
    LINE4 = r"<MainSupplyVoltage>([.\d]+)</MainSupplyVoltage>"
    LINE5 = r"<Samples>(\d+)</Samples>"
    LINE6 = r"<Bytes>(\d+)</Bytes>"
    LINE7 = r"<BytesFree>(\d+)</BytesFree>"

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """
        # Initialize
        single_var_matches  = {
            SBE54tpsStatusDataParticleKey.DEVICE_TYPE: None,
            SBE54tpsStatusDataParticleKey.SERIAL_NUMBER: None,
            SBE54tpsStatusDataParticleKey.TIME: None,
            SBE54tpsStatusDataParticleKey.EVENT_COUNT: None,
            SBE54tpsStatusDataParticleKey.MAIN_SUPPLY_VOLTAGE: None,
            SBE54tpsStatusDataParticleKey.NUMBER_OF_SAMPLES: None,
            SBE54tpsStatusDataParticleKey.BYTES_USED: None,
            SBE54tpsStatusDataParticleKey.BYTES_FREE: None
        }

        multi_var_matchers  = {
            re.compile(self.LINE1): [
                SBE54tpsStatusDataParticleKey.DEVICE_TYPE,
                SBE54tpsStatusDataParticleKey.SERIAL_NUMBER
            ],
            re.compile(self.LINE2): [
                SBE54tpsStatusDataParticleKey.TIME
            ],
            re.compile(self.LINE3): [
                SBE54tpsStatusDataParticleKey.EVENT_COUNT
            ],
            re.compile(self.LINE4): [
                SBE54tpsStatusDataParticleKey.MAIN_SUPPLY_VOLTAGE
            ],
            re.compile(self.LINE5): [
                SBE54tpsStatusDataParticleKey.NUMBER_OF_SAMPLES
            ],
            re.compile(self.LINE6): [
                SBE54tpsStatusDataParticleKey.BYTES_USED
            ],
            re.compile(self.LINE7): [
                SBE54tpsStatusDataParticleKey.BYTES_FREE
            ]
        }

        for line in self.raw_data.split(NEWLINE):
            for (matcher, keys) in multi_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    index = 0
                    for key in keys:
                        index = index + 1
                        val = match.group(index)

                        # str
                        if key in [
                            SBE54tpsStatusDataParticleKey.DEVICE_TYPE,
                        ]:
                            single_var_matches[key] = val

                        # int
                        elif key in [
                            SBE54tpsStatusDataParticleKey.SERIAL_NUMBER,
                            SBE54tpsStatusDataParticleKey.EVENT_COUNT,
                            SBE54tpsStatusDataParticleKey.NUMBER_OF_SAMPLES,
                            SBE54tpsStatusDataParticleKey.BYTES_USED,
                            SBE54tpsStatusDataParticleKey.BYTES_FREE
                        ]:
                            single_var_matches[key] = int(val)

                        #float
                        elif key in [
                            SBE54tpsStatusDataParticleKey.MAIN_SUPPLY_VOLTAGE
                        ]:
                            single_var_matches[key] = float(val)

                        # datetime
                        elif key in [
                            SBE54tpsStatusDataParticleKey.TIME
                        ]:
                            # yyyy-mm-ddThh:mm:ss
                            single_var_matches[key] = val
                            py_timestamp = time.strptime(val, "%Y-%m-%dT%H:%M:%S")
                            self.set_internal_timestamp(unix_time=time.mktime(py_timestamp))

                        else:
                            raise SampleException("Unknown variable type in SBE54tpsStatusDataParticle._build_parsed_values")

        result = []
        for (key, value) in single_var_matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result

class SBE54tpsConfigurationDataParticleKey(BaseEnum):
    DEVICE_TYPE = "device_type"
    SERIAL_NUMBER = "serial_number"
    ACQ_OSC_CAL_DATE = "calibration_date_acq_crystal"
    FRA0 = "acq_crystal_coeff_fra0"
    FRA1 = "acq_crystal_coeff_fra1"
    FRA2 = "acq_crystal_coeff_fra2"
    FRA3 = "acq_crystal_coeff_fra3"
    PRESSURE_SERIAL_NUM = "pressure_sensor_serial_number"
    PRESSURE_CAL_DATE = "calibration_date_pressure"
    PU0 = "press_coeff_pu0"
    PY1 = "press_coeff_py1"
    PY2 = "press_coeff_py2"
    PY3 = "press_coeff_py3"
    PC1 = "press_coeff_pc1"
    PC2 = "press_coeff_pc2"
    PC3 = "press_coeff_pc3"
    PD1 = "press_coeff_pd1"
    PD2 = "press_coeff_pd2"
    PT1 = "press_coeff_pt1"
    PT2 = "press_coeff_pt2"
    PT3 = "press_coeff_pt3"
    PT4 = "press_coeff_pt4"
    PRESSURE_OFFSET = "press_coeff_poffsett" # pisa
    PRESSURE_RANGE = "pressure_sensor_range" # pisa
    BATTERY_TYPE = "battery_type"
    BAUD_RATE = "baud_rate"
    UPLOAD_TYPE = "upload_type"
    ENABLE_ALERTS = "enable_alerts"
    SAMPLE_PERIOD = "sample_period"

class SBE54tpsConfigurationDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.PREST_CONFIGURATION_DATA
    
    LINE1 = r"<ConfigurationData DeviceType='([^']+)' SerialNumber='(\d+)'>"
    LINE2 = r"<AcqOscCalDate>([0-9\-]+)</AcqOscCalDate>"
    LINE3 = r"<FRA0>([0-9E+-.]+)</FRA0>"
    LINE4 = r"<FRA1>([0-9E+-.]+)</FRA1>"
    LINE5 = r"<FRA2>([0-9E+-.]+)</FRA2>"
    LINE6 = r"<FRA3>([0-9E+-.]+)</FRA3>"
    LINE7 = r"<PressureSerialNum>(\d+)</PressureSerialNum>"
    LINE8 = r"<PressureCalDate>([0-9\-]+)</PressureCalDate>"
    LINE9 = r"<pu0>([0-9E+-.]+)</pu0>"
    LINE10 = r"<py1>([0-9E+-.]+)</py1>"
    LINE11 = r"<py2>([0-9E+-.]+)</py2>"
    LINE12 = r"<py3>([0-9E+-.]+)</py3>"
    LINE13 = r"<pc1>([0-9E+-.]+)</pc1>"
    LINE14 = r"<pc2>([0-9E+-.]+)</pc2>"
    LINE15 = r"<pc3>([0-9E+-.]+)</pc3>"
    LINE16 = r"<pd1>([0-9E+-.]+)</pd1>"
    LINE17 = r"<pd2>([0-9E+-.]+)</pd2>"
    LINE18 = r"<pt1>([0-9E+-.]+)</pt1>"
    LINE19 = r"<pt2>([0-9E+-.]+)</pt2>"
    LINE20 = r"<pt3>([0-9E+-.]+)</pt3>"
    LINE21 = r"<pt4>([0-9E+-.]+)</pt4>"
    LINE22 = r"<poffset>([0-9E+-.]+)</poffset>"
    LINE23 = r"<prange>([0-9E+-.]+)</prange>"
    LINE24 = r"batteryType='(\d+)'"
    LINE25 = r"baudRate='(\d+)'"
    LINE26 = r"enableAlerts='(\d+)'"
    LINE27 = r"uploadType='(\d+)'"
    LINE28 = r"samplePeriod='(\d+)'"

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """

        # Initialize
        single_var_matches  = {
            SBE54tpsConfigurationDataParticleKey.DEVICE_TYPE: None,
            SBE54tpsConfigurationDataParticleKey.SERIAL_NUMBER: None,
            SBE54tpsConfigurationDataParticleKey.ACQ_OSC_CAL_DATE: None,
            SBE54tpsConfigurationDataParticleKey.FRA0: None,
            SBE54tpsConfigurationDataParticleKey.FRA1: None,
            SBE54tpsConfigurationDataParticleKey.FRA2: None,
            SBE54tpsConfigurationDataParticleKey.FRA3: None,
            SBE54tpsConfigurationDataParticleKey.PRESSURE_SERIAL_NUM: None,
            SBE54tpsConfigurationDataParticleKey.PRESSURE_CAL_DATE: None,
            SBE54tpsConfigurationDataParticleKey.PU0: None,
            SBE54tpsConfigurationDataParticleKey.PY1: None,
            SBE54tpsConfigurationDataParticleKey.PY2: None,
            SBE54tpsConfigurationDataParticleKey.PY3: None,
            SBE54tpsConfigurationDataParticleKey.PC1: None,
            SBE54tpsConfigurationDataParticleKey.PC2: None,
            SBE54tpsConfigurationDataParticleKey.PC3: None,
            SBE54tpsConfigurationDataParticleKey.PD1: None,
            SBE54tpsConfigurationDataParticleKey.PD2: None,
            SBE54tpsConfigurationDataParticleKey.PT1: None,
            SBE54tpsConfigurationDataParticleKey.PT2: None,
            SBE54tpsConfigurationDataParticleKey.PT3: None,
            SBE54tpsConfigurationDataParticleKey.PT4: None,
            SBE54tpsConfigurationDataParticleKey.PRESSURE_OFFSET: None,
            SBE54tpsConfigurationDataParticleKey.PRESSURE_RANGE: None,
            SBE54tpsConfigurationDataParticleKey.BATTERY_TYPE: None,
            SBE54tpsConfigurationDataParticleKey.BAUD_RATE: None,
            SBE54tpsConfigurationDataParticleKey.ENABLE_ALERTS: None,
            SBE54tpsConfigurationDataParticleKey.UPLOAD_TYPE: None,
            SBE54tpsConfigurationDataParticleKey.SAMPLE_PERIOD: None
        }

        multi_var_matchers  = {
            re.compile(self.LINE1): [
                SBE54tpsConfigurationDataParticleKey.DEVICE_TYPE,
                SBE54tpsConfigurationDataParticleKey.SERIAL_NUMBER
            ],
            re.compile(self.LINE2): [
                SBE54tpsConfigurationDataParticleKey.ACQ_OSC_CAL_DATE
            ],
            re.compile(self.LINE3): [
                SBE54tpsConfigurationDataParticleKey.FRA0
            ],
            re.compile(self.LINE4): [
                SBE54tpsConfigurationDataParticleKey.FRA1
            ],
            re.compile(self.LINE5): [
                SBE54tpsConfigurationDataParticleKey.FRA2
            ],
            re.compile(self.LINE6): [
                SBE54tpsConfigurationDataParticleKey.FRA3
            ],
            re.compile(self.LINE7): [
                SBE54tpsConfigurationDataParticleKey.PRESSURE_SERIAL_NUM
            ],
            re.compile(self.LINE8): [
                SBE54tpsConfigurationDataParticleKey.PRESSURE_CAL_DATE
            ],
            re.compile(self.LINE9): [
                SBE54tpsConfigurationDataParticleKey.PU0
            ],
            re.compile(self.LINE10): [
                SBE54tpsConfigurationDataParticleKey.PY1
            ],
            re.compile(self.LINE11): [
                SBE54tpsConfigurationDataParticleKey.PY2
            ],
            re.compile(self.LINE12): [
                SBE54tpsConfigurationDataParticleKey.PY3
            ],
            re.compile(self.LINE13): [
                SBE54tpsConfigurationDataParticleKey.PC1
            ],
            re.compile(self.LINE14): [
                SBE54tpsConfigurationDataParticleKey.PC2
            ],
            re.compile(self.LINE15): [
                SBE54tpsConfigurationDataParticleKey.PC3
            ],
            re.compile(self.LINE16): [
                SBE54tpsConfigurationDataParticleKey.PD1
            ],
            re.compile(self.LINE17): [
                SBE54tpsConfigurationDataParticleKey.PD2
            ],
            re.compile(self.LINE18): [
                SBE54tpsConfigurationDataParticleKey.PT1
            ],
            re.compile(self.LINE19): [
                SBE54tpsConfigurationDataParticleKey.PT2
            ],
            re.compile(self.LINE20): [
                SBE54tpsConfigurationDataParticleKey.PT3
            ],
            re.compile(self.LINE21): [
                SBE54tpsConfigurationDataParticleKey.PT4
            ],
            re.compile(self.LINE22): [
                SBE54tpsConfigurationDataParticleKey.PRESSURE_OFFSET
            ],
            re.compile(self.LINE23): [
                SBE54tpsConfigurationDataParticleKey.PRESSURE_RANGE
            ],
            re.compile(self.LINE24): [
                SBE54tpsConfigurationDataParticleKey.BATTERY_TYPE
            ],
            re.compile(self.LINE25): [
                SBE54tpsConfigurationDataParticleKey.BAUD_RATE
            ],
            re.compile(self.LINE26): [
                SBE54tpsConfigurationDataParticleKey.ENABLE_ALERTS
            ],
            re.compile(self.LINE27): [
                SBE54tpsConfigurationDataParticleKey.UPLOAD_TYPE
            ],
            re.compile(self.LINE28): [
                SBE54tpsConfigurationDataParticleKey.SAMPLE_PERIOD
            ]
        }

        for line in self.raw_data.split(NEWLINE):
            for (matcher, keys) in multi_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    index = 0
                    for key in keys:
                        index = index + 1
                        val = match.group(index)

                        # str
                        if key in [
                            SBE54tpsConfigurationDataParticleKey.DEVICE_TYPE,
                            SBE54tpsConfigurationDataParticleKey.PRESSURE_CAL_DATE,
                            SBE54tpsConfigurationDataParticleKey.ACQ_OSC_CAL_DATE
                        ]:
                            single_var_matches[key] = val

                        # int
                        elif key in [
                            SBE54tpsConfigurationDataParticleKey.SERIAL_NUMBER,
                            SBE54tpsConfigurationDataParticleKey.PRESSURE_SERIAL_NUM,
                            SBE54tpsConfigurationDataParticleKey.BATTERY_TYPE,
                            SBE54tpsConfigurationDataParticleKey.UPLOAD_TYPE,
                            SBE54tpsConfigurationDataParticleKey.SAMPLE_PERIOD,
                            SBE54tpsConfigurationDataParticleKey.BAUD_RATE
                        ]:
                            single_var_matches[key] = int(val)

                        # bool
                        elif key in [
                            SBE54tpsConfigurationDataParticleKey.ENABLE_ALERTS
                        ]:
                            single_var_matches[key] = bool(int(val))

                        #float
                        elif key in [
                            SBE54tpsConfigurationDataParticleKey.FRA0,
                            SBE54tpsConfigurationDataParticleKey.FRA1,
                            SBE54tpsConfigurationDataParticleKey.FRA2,
                            SBE54tpsConfigurationDataParticleKey.FRA3,
                            SBE54tpsConfigurationDataParticleKey.PU0,
                            SBE54tpsConfigurationDataParticleKey.PY1,
                            SBE54tpsConfigurationDataParticleKey.PY2,
                            SBE54tpsConfigurationDataParticleKey.PY3,
                            SBE54tpsConfigurationDataParticleKey.PC1,
                            SBE54tpsConfigurationDataParticleKey.PC2,
                            SBE54tpsConfigurationDataParticleKey.PC3,
                            SBE54tpsConfigurationDataParticleKey.PD1,
                            SBE54tpsConfigurationDataParticleKey.PD2,
                            SBE54tpsConfigurationDataParticleKey.PT1,
                            SBE54tpsConfigurationDataParticleKey.PT2,
                            SBE54tpsConfigurationDataParticleKey.PT3,
                            SBE54tpsConfigurationDataParticleKey.PT4,
                            SBE54tpsConfigurationDataParticleKey.PRESSURE_OFFSET,
                            SBE54tpsConfigurationDataParticleKey.PRESSURE_RANGE
                        ]:
                            single_var_matches[key] = float(val)

                        else:
                            raise SampleException("Unknown variable type in SBE54tpsConfigurationDataParticle._build_parsed_values")

        result = []
        for (key, value) in single_var_matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result

class SBE54tpsEventCounterDataParticleKey(BaseEnum):
    NUMBER_EVENTS = "number_events"
    MAX_STACK = "max_stack"
    DEVICE_TYPE = "device_type"
    SERIAL_NUMBER = "serial_number"
    POWER_ON_RESET = "power_on_reset"
    POWER_FAIL_RESET = "power_fail_reset"
    SERIAL_BYTE_ERROR = "serial_byte_error"
    COMMAND_BUFFER_OVERFLOW = "command_buffer_overflow"
    SERIAL_RECEIVE_OVERFLOW = "serial_receive_overflow"
    LOW_BATTERY = "low_battery"
    SIGNAL_ERROR = "signal_error"
    ERROR_10 = "error_10"
    ERROR_12 = "error_12"

class SBE54tpsEventCounterDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.PREST_EVENT_COUNTER

    LINE1 = r"<EventSummary numEvents='(573)' maxStack='(354)'/>"
    LINE2 = r"<EventList DeviceType='([^']+)' SerialNumber='(\d+)'>"
    LINE3 = r"<Event type='PowerOnReset' count='(\d+)'/>"
    LINE4 = r"<Event type='PowerFailReset' count='(\d+)'/>"
    LINE5 = r"<Event type='SerialByteErr' count='(\d+)'/>"
    LINE6 = r"<Event type='CMDBuffOflow' count='(\d+)'/>"
    LINE7 = r"<Event type='SerialRxOflow' count='(\d+)'/>"
    LINE8 = r"<Event type='LowBattery' count='(\d+)'/>"
    LINE9 = r"<Event type='SignalErr' count='(\d+)'/>"
    LINE10 = r"<Event type='Error10' count='(\d+)'/>"
    LINE11 = r"<Event type='Error12' count='(\d+)'/>"

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """

        # Initialize
        single_var_matches  = {
            SBE54tpsEventCounterDataParticleKey.NUMBER_EVENTS: 0,
            SBE54tpsEventCounterDataParticleKey.MAX_STACK: 0,
            SBE54tpsEventCounterDataParticleKey.DEVICE_TYPE: None,
            SBE54tpsEventCounterDataParticleKey.SERIAL_NUMBER: None,
            SBE54tpsEventCounterDataParticleKey.POWER_ON_RESET: 0,
            SBE54tpsEventCounterDataParticleKey.POWER_FAIL_RESET: 0,
            SBE54tpsEventCounterDataParticleKey.SERIAL_BYTE_ERROR: 0,
            SBE54tpsEventCounterDataParticleKey.COMMAND_BUFFER_OVERFLOW: 0,
            SBE54tpsEventCounterDataParticleKey.SERIAL_RECEIVE_OVERFLOW: 0,
            SBE54tpsEventCounterDataParticleKey.LOW_BATTERY: 0,
            SBE54tpsEventCounterDataParticleKey.SIGNAL_ERROR: 0,
            SBE54tpsEventCounterDataParticleKey.ERROR_10: 0,
            SBE54tpsEventCounterDataParticleKey.ERROR_12: 0
        }

        multi_var_matchers  = {
            re.compile(self.LINE1): [
                SBE54tpsEventCounterDataParticleKey.NUMBER_EVENTS,
                SBE54tpsEventCounterDataParticleKey.MAX_STACK
            ],
            re.compile(self.LINE2): [
                SBE54tpsEventCounterDataParticleKey.DEVICE_TYPE,
                SBE54tpsEventCounterDataParticleKey.SERIAL_NUMBER
            ],
            re.compile(self.LINE3): [
                SBE54tpsEventCounterDataParticleKey.POWER_ON_RESET
            ],
            re.compile(self.LINE4): [
                SBE54tpsEventCounterDataParticleKey.POWER_FAIL_RESET
            ],
            re.compile(self.LINE5): [
                SBE54tpsEventCounterDataParticleKey.SERIAL_BYTE_ERROR
            ],
            re.compile(self.LINE6): [
                SBE54tpsEventCounterDataParticleKey.COMMAND_BUFFER_OVERFLOW
            ],
            re.compile(self.LINE7): [
                SBE54tpsEventCounterDataParticleKey.SERIAL_RECEIVE_OVERFLOW
            ],
            re.compile(self.LINE8): [
                SBE54tpsEventCounterDataParticleKey.LOW_BATTERY
            ],
            re.compile(self.LINE9): [
                SBE54tpsEventCounterDataParticleKey.SIGNAL_ERROR
            ],
            re.compile(self.LINE10): [
                SBE54tpsEventCounterDataParticleKey.ERROR_10
            ],
            re.compile(self.LINE11): [
                SBE54tpsEventCounterDataParticleKey.ERROR_12
            ]
        }

        for line in self.raw_data.split(NEWLINE):
            for (matcher, keys) in multi_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    index = 0
                    for key in keys:
                        index = index + 1
                        val = match.group(index)
                        log.debug("KEY [%s] VAL[%s]", key, val)
                        # str
                        if key in [
                            SBE54tpsEventCounterDataParticleKey.DEVICE_TYPE
                            ]:
                            single_var_matches[key] = match.group(index)

                        # int
                        elif key in [
                            SBE54tpsEventCounterDataParticleKey.NUMBER_EVENTS,
                            SBE54tpsEventCounterDataParticleKey.MAX_STACK,
                            SBE54tpsEventCounterDataParticleKey.SERIAL_NUMBER,
                            SBE54tpsEventCounterDataParticleKey.POWER_ON_RESET,
                            SBE54tpsEventCounterDataParticleKey.POWER_FAIL_RESET,
                            SBE54tpsEventCounterDataParticleKey.SERIAL_BYTE_ERROR,
                            SBE54tpsEventCounterDataParticleKey.COMMAND_BUFFER_OVERFLOW,
                            SBE54tpsEventCounterDataParticleKey.SERIAL_RECEIVE_OVERFLOW,
                            SBE54tpsEventCounterDataParticleKey.LOW_BATTERY,
                            SBE54tpsEventCounterDataParticleKey.SIGNAL_ERROR,
                            SBE54tpsEventCounterDataParticleKey.ERROR_10,
                            SBE54tpsEventCounterDataParticleKey.ERROR_12
                        ]:
                            single_var_matches[key] = int(match.group(index))
                        else:
                            raise SampleException("Unknown variable type in SBE54tpsEventCounterDataParticle._build_parsed_values")

        result = []
        for (key, value) in single_var_matches.iteritems():
            log.debug("SETTING %s = %s", key, value)
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result

class SBE54tpsHardwareDataParticleKey(BaseEnum):
    DEVICE_TYPE = "device_type"
    SERIAL_NUMBER = "serial_number"
    MANUFACTURER = "manufacturer"
    FIRMWARE_VERSION = "firmware_version"
    FIRMWARE_DATE = "firmware_date"
    HARDWARE_VERSION = "hardware_version"
    PCB_SERIAL_NUMBER = "pcb_serial_number"
    PCB_TYPE = "pcb_type"
    MANUFACTUR_DATE = "manufacture_date"

class SBE54tpsHardwareDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.PREST_HARDWARE_DATA
    
    LINE1 = r"<HardwareData DeviceType='([^']+)' SerialNumber='(\d+)'>"
    LINE2 = r"<Manufacturer>([^<]+)</Manufacturer>"
    LINE3 = r"<FirmwareVersion>([^<]+)</FirmwareVersion>"
    LINE4 = r"<FirmwareDate>([^<]+)</FirmwareDate>"
    LINE5 = r"<HardwareVersion>([^<]+)</HardwareVersion>"
    LINE6 = r"<PCBSerialNum>([^<]+)</PCBSerialNum>"
    LINE7 = r"<PCBType>([^<]+)</PCBType>"
    LINE8 = r"<MfgDate>([^<]+)</MfgDate>"

    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """
        # Initialize
        single_var_matches  = {
            SBE54tpsHardwareDataParticleKey.DEVICE_TYPE: None,
            SBE54tpsHardwareDataParticleKey.SERIAL_NUMBER: None,
            SBE54tpsHardwareDataParticleKey.MANUFACTURER: None,
            SBE54tpsHardwareDataParticleKey.FIRMWARE_VERSION: None,
            SBE54tpsHardwareDataParticleKey.FIRMWARE_DATE: None,
            SBE54tpsHardwareDataParticleKey.HARDWARE_VERSION: [],
            SBE54tpsHardwareDataParticleKey.PCB_SERIAL_NUMBER: [],
            SBE54tpsHardwareDataParticleKey.PCB_TYPE: None,
            SBE54tpsHardwareDataParticleKey.MANUFACTUR_DATE: None
        }

        multi_var_matchers  = {
            re.compile(self.LINE1): [
                SBE54tpsHardwareDataParticleKey.DEVICE_TYPE,
                SBE54tpsHardwareDataParticleKey.SERIAL_NUMBER
            ],
            re.compile(self.LINE2): [
                SBE54tpsHardwareDataParticleKey.MANUFACTURER
            ],
            re.compile(self.LINE3): [
                SBE54tpsHardwareDataParticleKey.FIRMWARE_VERSION
            ],
            re.compile(self.LINE4): [
                SBE54tpsHardwareDataParticleKey.FIRMWARE_DATE
            ],
            re.compile(self.LINE5): [
                SBE54tpsHardwareDataParticleKey.HARDWARE_VERSION
            ],
            re.compile(self.LINE6): [
                SBE54tpsHardwareDataParticleKey.PCB_SERIAL_NUMBER
            ],
            re.compile(self.LINE7): [
                SBE54tpsHardwareDataParticleKey.PCB_TYPE
            ],
            re.compile(self.LINE8): [
                SBE54tpsHardwareDataParticleKey.MANUFACTUR_DATE
            ]
        }

        for line in self.raw_data.split(NEWLINE):
            for (matcher, keys) in multi_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    index = 0
                    for key in keys:
                        index = index + 1
                        val = match.group(index)

                        # str
                        if key in [
                            SBE54tpsHardwareDataParticleKey.DEVICE_TYPE,
                            SBE54tpsHardwareDataParticleKey.MANUFACTURER,
                            SBE54tpsHardwareDataParticleKey.FIRMWARE_VERSION,
                            SBE54tpsHardwareDataParticleKey.FIRMWARE_VERSION,
                            SBE54tpsHardwareDataParticleKey.HARDWARE_VERSION,
                            SBE54tpsHardwareDataParticleKey.PCB_SERIAL_NUMBER,
                            SBE54tpsHardwareDataParticleKey.PCB_TYPE,
                            SBE54tpsHardwareDataParticleKey.MANUFACTUR_DATE,
                            SBE54tpsHardwareDataParticleKey.FIRMWARE_DATE,
                        ]:
                            single_var_matches[key] = val

                        # int
                        elif key in [
                            SBE54tpsHardwareDataParticleKey.SERIAL_NUMBER
                        ]:
                            single_var_matches[key] = int(val)

        result = []
        for (key, value) in single_var_matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result

class SBE54tpsSampleDataParticleKey(BaseEnum):
    SAMPLE_NUMBER = "sample_number"
    SAMPLE_TYPE = "sample_type"
    INST_TIME = "date_time_string"
    PRESSURE = "absolute_pressure" # psi
    PRESSURE_TEMP = "pressure_temp"

class SBE54tpsSampleDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.PREST_REAL_TIME
    
    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """
        # Initialize
        single_var_matches  = {
            SBE54tpsSampleDataParticleKey.SAMPLE_NUMBER: None,
            SBE54tpsSampleDataParticleKey.SAMPLE_TYPE: None,
            SBE54tpsSampleDataParticleKey.INST_TIME: None,
            SBE54tpsSampleDataParticleKey.PRESSURE: None,
            SBE54tpsSampleDataParticleKey.PRESSURE_TEMP: None
        }

        multi_var_matchers  = {
            re.compile(r"<Sample Num='(\d+)' Type='([^']+)'>"): [
                SBE54tpsSampleDataParticleKey.SAMPLE_NUMBER,
                SBE54tpsSampleDataParticleKey.SAMPLE_TYPE
            ],
            re.compile(r"<Time>([^<]+)</Time>"): [
                SBE54tpsSampleDataParticleKey.INST_TIME
            ],
            re.compile(r"<PressurePSI>([0-9.+-]+)</PressurePSI>"): [
                SBE54tpsSampleDataParticleKey.PRESSURE
            ],
            re.compile(r"<PTemp>([0-9.+-]+)</PTemp>"): [
                SBE54tpsSampleDataParticleKey.PRESSURE_TEMP
            ]
        }

        for line in self.raw_data.split(NEWLINE):
            for (matcher, keys) in multi_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    index = 0
                    for key in keys:
                        index = index + 1
                        val = match.group(index)

                        # str
                        if key in [
                            SBE54tpsSampleDataParticleKey.SAMPLE_TYPE,
                            SBE54tpsSampleDataParticleKey.INST_TIME
                        ]:
                            log.debug("SAMPLE_TYPE = %s", val)
                            single_var_matches[key] = val

                        # int
                        elif key in [
                            SBE54tpsSampleDataParticleKey.SAMPLE_NUMBER
                        ]:
                            single_var_matches[key] = int(val)

                        # float
                        elif key in [
                            SBE54tpsSampleDataParticleKey.PRESSURE,
                            SBE54tpsSampleDataParticleKey.PRESSURE_TEMP
                        ]:
                            single_var_matches[key] = float(val)

                        # date_time
                        elif key in [
                        ]:
                            # <Time>2012-11-07T12:21:25</Time>
                            # yyyy-mm-ddThh:mm:ss
                            text_timestamp = val
                            py_timestamp = time.strptime(text_timestamp, "%Y-%m-%dT%H:%M:%S")
                            timestamp = ntplib.system_to_ntp_time(time.mktime(py_timestamp))
                            single_var_matches[key] = timestamp

                        else:
                            raise SampleException("Unknown variable type in SBE54tpsConfigurationDataParticle._build_parsed_values")

        result = []
        for (key, value) in single_var_matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result

class SBE54tpsSampleRefOscDataParticleKey(BaseEnum):
    SET_TIMEOUT = "set_timeout"
    SET_TIMEOUT_MAX = "set_timeout_max"
    SET_TIMEOUT_ICD = "set_timeout_icd"
    SAMPLE_NUMBER = "sample_number"
    SAMPLE_TYPE = "sample_type"
    SAMPLE_TIMESTAMP = "date_time_string"
    REF_OSC_FREQ = "reference_oscillator_freq"
    PCB_TEMP_RAW = "pcb_thermistor_value"
    REF_ERROR_PPM = "reference_error"

class SBE54tpsSampleRefOscDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.PREST_REFERENCE_OSCILLATOR
    
    def _build_parsed_values(self):
        """
        Take something in the StatusData format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """
        # Initialize
        single_var_matches  = {
            SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT: None,
            SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_MAX: None,
            SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_ICD: None,
            SBE54tpsSampleRefOscDataParticleKey.SAMPLE_NUMBER: None,
            SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TYPE: None,
            SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TIMESTAMP: None,
            SBE54tpsSampleRefOscDataParticleKey.REF_OSC_FREQ: None,
            SBE54tpsSampleRefOscDataParticleKey.PCB_TEMP_RAW: None,
            SBE54tpsSampleRefOscDataParticleKey.REF_ERROR_PPM: None
        }

        multi_var_matchers  = {
            re.compile(r"<SetTimeout>([^<]+)</SetTimeout>"): [
                SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT
            ],
            re.compile(r"<SetTimeoutMax>([^<]+)</SetTimeoutMax>"): [
                SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_MAX
            ],
            re.compile(r"<SetTimeoutICD>([^<]+)</SetTimeoutICD>"): [
                SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_ICD
            ],
            re.compile(r"<Sample Num='([^']+)' Type='([^']+)'>"): [
                SBE54tpsSampleRefOscDataParticleKey.SAMPLE_NUMBER,
                SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TYPE
            ],
            re.compile(r"<Time>([^<]+)</Time>"): [
                SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TIMESTAMP
            ],
            re.compile(r"<RefOscFreq>([0-9.+-]+)</RefOscFreq>"): [
                SBE54tpsSampleRefOscDataParticleKey.REF_OSC_FREQ
            ],
            re.compile(r"<PCBTempRaw>([0-9.+-]+)</PCBTempRaw>"): [
                SBE54tpsSampleRefOscDataParticleKey.PCB_TEMP_RAW
            ],
            re.compile(r"<RefErrorPPM>([0-9.+-]+)</RefErrorPPM>"): [
                SBE54tpsSampleRefOscDataParticleKey.REF_ERROR_PPM
            ]
        }

        for line in self.raw_data.split(NEWLINE):
            for (matcher, keys) in multi_var_matchers.iteritems():
                match = matcher.match(line)
                if match:
                    index = 0
                    for key in keys:
                        index = index + 1
                        val = match.group(index)
                        log.debug("SAMPLE_TYPE = " + val)

                        # str
                        if key in [
                            SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TYPE
                        ]:
                            single_var_matches[key] = val

                        # int
                        elif key in [
                            SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT,
                            SBE54tpsSampleRefOscDataParticleKey.SAMPLE_NUMBER,
                            SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_MAX,
                            SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_ICD,
                            SBE54tpsSampleRefOscDataParticleKey.PCB_TEMP_RAW,
                        ]:
                            if(key == SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_MAX and val.lower() == 'off'):
                                val = 0
                            single_var_matches[key] = int(val)

                        # float
                        elif key in [
                            SBE54tpsSampleRefOscDataParticleKey.REF_OSC_FREQ,
                            SBE54tpsSampleRefOscDataParticleKey.REF_ERROR_PPM
                        ]:
                            single_var_matches[key] = float(val)

                        # date_time
                        elif key in [
                            SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TIMESTAMP
                        ]:
                            # <Time>2012-11-07T12:21:25</Time>
                            # yyyy-mm-ddThh:mm:ss
                            single_var_matches[key] = val
                            py_timestamp = time.strptime(val, "%Y-%m-%dT%H:%M:%S")
                            self.set_internal_timestamp(time.mktime(py_timestamp))

                        else:
                            raise SampleException("Unknown variable type in SBE54tpsConfigurationDataParticle._build_parsed_values")


        result = []
        for (key, value) in single_var_matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result

######################################### /PARTICLES #############################


###############################################################################
# Driver
###############################################################################

class SBE54PlusInstrumentDriver(SeaBirdInstrumentDriver):
    """
    SBEInstrumentDriver subclass
    Subclasses Seabird driver with connection state
    machine.
    """
    def __init__(self, evt_callback):
        """
        Driver constructor.
        @param evt_callback Driver process event callback.
        """
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
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)

###############################################################################
# Protocol
################################################################################

class Protocol(SeaBirdProtocol):
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
        SeaBirdProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER,                  self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT,                   self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER,               self._handler_unknown_discover)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER,                  self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT,                   self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE,       self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.RECOVER_AUTOSAMPLE,     self._handler_command_recover_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET,                    self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET,                    self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC,             self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SCHEDULED_CLOCK_SYNC,   self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS,         self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_CONFIGURATION_DATA, self._handler_command_get_configuration)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_STATUS_DATA,        self._handler_command_get_status)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_EVENT_COUNTER,      self._handler_command_get_event_counter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_HARDWARE_DATA,      self._handler_command_get_hardware)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT,           self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SAMPLE_REFERENCE_OSCILLATOR, self._handler_sample_ref_osc)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.TEST_EEPROM,            self._handler_command_test_eeprom)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_STATUS,         self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SCHEDULED_CLOCK_SYNC,   self._handler_autosample_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET_CONFIGURATION_DATA, self._handler_command_get_configuration)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET_STATUS_DATA,        self._handler_command_get_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET_EVENT_COUNTER,      self._handler_command_get_event_counter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET_HARDWARE_DATA,      self._handler_command_get_hardware)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER,                  self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT,                   self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET,                    self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE,        self._handler_autosample_stop_autosample)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER,            self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT,             self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT,   self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT,      self._handler_direct_access_stop_direct)

        # Build dictionaries for driver schema
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCmds.SET,                    self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_TIME,               self._build_set_command)
        self._add_build_handler(InstrumentCmds.GET_CONFIGURATION_DATA, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GET_STATUS_DATA,        self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GET_EVENT_COUNTER_DATA, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GET_HARDWARE_DATA,      self._build_simple_command)
        self._add_build_handler(InstrumentCmds.START_LOGGING,          self._build_simple_command)
        self._add_build_handler(InstrumentCmds.STOP_LOGGING,           self._build_simple_command)
        self._add_build_handler(InstrumentCmds.INIT_LOGGING,           self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SAMPLE_REFERENCE_OSCILLATOR,  self._build_simple_command)
        self._add_build_handler(InstrumentCmds.TEST_EEPROM,            self._build_simple_command)
        self._add_build_handler(InstrumentCmds.RESET_EC,               self._build_simple_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.SET,                    self._parse_set_response)
        self._add_response_handler(InstrumentCmds.SET_TIME,               self._parse_set_response)
        self._add_response_handler(InstrumentCmds.GET_CONFIGURATION_DATA, self._parse_gc_response)
        self._add_response_handler(InstrumentCmds.GET_STATUS_DATA,        self._parse_gs_response)
        self._add_response_handler(InstrumentCmds.GET_EVENT_COUNTER_DATA, self._parse_ec_response)
        self._add_response_handler(InstrumentCmds.GET_HARDWARE_DATA,      self._parse_hd_response)
        self._add_response_handler(InstrumentCmds.INIT_LOGGING,           self._parse_init_logging_response)
        self._add_response_handler(InstrumentCmds.SAMPLE_REFERENCE_OSCILLATOR,  self._parse_sample_ref_osc)
        self._add_response_handler(InstrumentCmds.TEST_EEPROM,            self._parse_test_eeprom)
        self._add_response_handler(InstrumentCmds.RESET_EC,               self._parse_reset_ec)
        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS, ProtocolEvent.ACQUIRE_STATUS)
        self._add_scheduler_event(ScheduledJob.CONFIGURATION_DATA, ProtocolEvent.GET_CONFIGURATION_DATA)
        self._add_scheduler_event(ScheduledJob.EVENT_COUNTER_DATA, ProtocolEvent.GET_EVENT_COUNTER)
        self._add_scheduler_event(ScheduledJob.HARDWARE_DATA, ProtocolEvent.GET_HARDWARE_DATA)
        self._add_scheduler_event(ScheduledJob.STATUS_DATA, ProtocolEvent.GET_STATUS_DATA)
        self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.SCHEDULED_CLOCK_SYNC)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        return_list = []

        sieve_matchers = [ STATUS_DATA_REGEX_MATCHER,
                           CONFIGURATION_DATA_REGEX_MATCHER,
                           EVENT_COUNTER_DATA_REGEX_MATCHER,
                           HARDWARE_DATA_REGEX_MATCHER,
                           SAMPLE_DATA_REGEX_MATCHER,
                           ENGINEERING_DATA_MATCHER ]

        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        log.debug("%%% IN _filter_capabilities in state " + repr(self._protocol_fsm.get_current_state()))

        log.debug("%%% - EVENTS_IN = " + repr(events))
        events_out = [x for x in events if Capability.has(x)]
        log.debug("%%% - EVENTS_OUT = " + repr(events_out))

        return events_out

    def _parse_set_response(self, response, prompt):
        """
        Parse handler for set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """
        log.debug("_parse_set_response RESPONSE = " + str(response) + "/PROMPT = " + str(prompt))
        if ('Error' in response):
            raise InstrumentParameterException('Protocol._parse_set_response : Set command not recognized: %s' % response)

    def _parse_gc_response(self, response, prompt):

        response = response.replace("S>" + NEWLINE, "")
        response = response.replace("<Executed/>" + NEWLINE, "")
        response = response.replace(InstrumentCmds.GET_CONFIGURATION_DATA + NEWLINE, "")
        response = response.replace("S>", "")

        log.debug("IN _parse_gc_response RESPONSE = " + repr(response))
        return response

    def _parse_gs_response(self, response, prompt):
        response = response.replace("S>" + NEWLINE, "")
        response = response.replace("<Executed/>" + NEWLINE, "")
        response = response.replace(InstrumentCmds.GET_STATUS_DATA + NEWLINE, "")
        response = response.replace("S>", "")

        log.debug("IN _parse_gs_response RESPONSE = " + repr(response))
        return response

    def _parse_ec_response(self, response, prompt):
        response = response.replace("S>" + NEWLINE, "")
        response = response.replace("<Executed/>" + NEWLINE, "")
        response = response.replace(InstrumentCmds.GET_EVENT_COUNTER_DATA + NEWLINE, "")
        response = response.replace("S>", "")

        log.debug("IN _parse_ec_response RESPONSE = " + repr(response))
        return response

    def _parse_hd_response(self, response, prompt):
        response = response.replace("S>" + NEWLINE, "")
        response = response.replace("<Executed/>" + NEWLINE, "")
        response = response.replace(InstrumentCmds.GET_HARDWARE_DATA + NEWLINE, "")
        response = response.replace("S>", "")

        log.debug("IN _parse_hd_response RESPONSE = " + repr(response))
        return response

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        log.debug("%%% IN _handler_unknown_enter")
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result)
        @retval (next_state, result), (ProtocolState.COMMAND or
        State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """
        timeout = kwargs.get('timeout', TIMEOUT)

        log.debug("_handler_unknown_discover")
        next_state = None
        next_agent_state = None

        logging = self._is_logging()
        log.debug("are we logging? %s" % logging)

        if(logging == None):
            raise InstrumentProtocolException('_handler_unknown_discover - unable to to determine state')

        elif(logging):
            next_state = ProtocolState.AUTOSAMPLE
            next_agent_state = ResourceAgentState.STREAMING

        else:
            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.IDLE

        log.debug("_handler_unknown_discover. result start: %s" % next_state)
        return (next_state, next_agent_state)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        log.debug("%%% IN _handler_unknown_exit")
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

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        log.debug("%%% IN _handler_command_enter")
        #self._restore_da_params()
        self._update_params()

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from SBE54TPS.
        @retval (next_state, result) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """

        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 45 # samples can take a long time


        """
        to do aquire sample, will need to:
        stop
        getcd to learn current sampling period
        SetSamplePeriod=1
        collect a sample
        stop
        restore sample period.
        """

        #result = self._do_cmd_resp(InstrumentCmds.TAKE_SAMPLE, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Run all Get?? commands.  Concat command results and return
        @param args:
        @param kwargs:
        @return:
        """
        log.debug("%%% IN _handler_command_aquire_status")

        timeout = kwargs.get('timeout', TIMEOUT)

        next_state = None
        next_agent_state = None
        result1 = self._do_cmd_resp(InstrumentCmds.GET_CONFIGURATION_DATA, timeout=timeout)
        result2 = self._do_cmd_resp(InstrumentCmds.GET_STATUS_DATA, timeout=timeout)
        result3 = self._do_cmd_resp(InstrumentCmds.GET_EVENT_COUNTER_DATA, timeout=timeout)
        result4 = self._do_cmd_resp(InstrumentCmds.GET_HARDWARE_DATA, timeout=timeout)

        result = result1 + result2 + result3 + result4

        log.debug("RESULT(RETURNED) = " + str(result))
        return (next_state, (next_agent_state, result))

    def _handler_command_get_configuration(self, *args, **kwargs):
        """
        Run the GetCC Command
        """
        timeout = kwargs.get('timeout', TIMEOUT)

        next_state = None
        next_agent_state = None
        result = self._do_cmd_resp(InstrumentCmds.GET_CONFIGURATION_DATA, timeout=timeout)

        return (next_state, (next_agent_state, result))

    def _handler_command_get_status(self, *args, **kwargs):
        """
        Run the GetCC Command
        """
        timeout = kwargs.get('timeout', TIMEOUT)

        next_state = None
        next_agent_state = None
        result = self._do_cmd_resp(InstrumentCmds.GET_STATUS_DATA, timeout=timeout)

        return (next_state, (next_agent_state, result))

    def _handler_command_get_event_counter(self, *args, **kwargs):
        """
        Run the GetCC Command
        """
        timeout = kwargs.get('timeout', TIMEOUT)

        next_state = None
        next_agent_state = None
        result = self._do_cmd_resp(InstrumentCmds.GET_EVENT_COUNTER_DATA, timeout=timeout)

        return (next_state, (next_agent_state, result))

    def _handler_command_get_hardware(self, *args, **kwargs):
        """
        Run the GetCC Command
        """
        timeout = kwargs.get('timeout', TIMEOUT)

        next_state = None
        next_agent_state = None
        result = self._do_cmd_resp(InstrumentCmds.GET_HARDWARE_DATA, timeout=timeout)

        return (next_state, (next_agent_state, result))

    def _handler_command_start_direct(self, *args, **kwargs):
        """
        """
        next_state = None
        result = None

        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        log.debug("_handler_command_start_direct: entering DA mode")
        return (next_state, (next_agent_state, result))

    def _handler_command_recover_autosample(self, *args, **kwargs):
        """
        Reenter autosample mode.  Used when our data handler detects
        as data sample.
        @retval (next_state, result) tuple, (None, sample dict).
        """
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING
        result = None

        self._driver_event(DriverAsyncEvent.AGENT_EVENT, ResourceAgentEvent.CHANGE_STATE, next_agent_state)
        return (next_state, None)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Enter autosample mode.
        @retval (next_state, result) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.

        <Executed/>
        S>start
        start
        <Executed/>
        """
        log.debug("%%% IN _handler_command_start_autosample")

        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        result = self._do_cmd_resp(InstrumentCmds.START_LOGGING, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        log.debug("%%% IN _handler_command_exit")
        pass

    def _handler_command_test_eeprom(self, *args, **kwargs):
        log.debug("%%% in _handler_command_test_eeprom")

        next_state = None
        next_agent_state = None
        result = None

        kwargs['expected_prompt'] = "S>"
        kwargs['timeout'] = 200
        result = self._do_cmd_resp(InstrumentCmds.TEST_EEPROM, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _parse_test_eeprom(self, response, prompt):
        """
        @return: True or False
        """
        if prompt != 'S>':
            raise InstrumentProtocolException('TEST_EEPROM command not recognized: %s' % response)

        if "PASSED" in response:
            return True
        else:
            return False

    def _parse_reset_ec(self, response, prompt):
        """
        @return: True or False
        """
        if prompt != 'S>':
            raise InstrumentProtocolException('RESET_EC command not recognized: %s' % response)

        if "<Executed/>" in response:
            return True
        else:
            return False

    def _handler_command_reset_ec(self, *args, **kwargs):

        log.debug("%%% in _handler_sample_ref_osc")

        next_state = None
        next_agent_state = None
        result = None

        kwargs['expected_prompt'] = "S>"
        kwargs['timeout'] = 10
        result = self._do_cmd_resp(InstrumentCmds.RESET_EC, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_sample_ref_osc(self, *args, **kwargs):

        log.debug("%%% in _handler_sample_ref_osc")

        next_state = None
        next_agent_state = None
        result = None

        kwargs['expected_prompt'] = "S>"
        kwargs['timeout'] = 200
        result = self._do_cmd_resp(InstrumentCmds.SAMPLE_REFERENCE_OSCILLATOR, *args, **kwargs)


        return (next_state, (next_agent_state, result))

    def _parse_sample_ref_osc(self, response, prompt):

        if prompt != 'S>':
            raise InstrumentProtocolException('SAMPLE_REFERENCE_OSCILLATOR command not recognized: %s' % response)

        response = response.replace("S>" + NEWLINE, "")
        response = response.replace("<Executed/>" + NEWLINE, "")
        response = response.replace(InstrumentCmds.SAMPLE_REFERENCE_OSCILLATOR + NEWLINE, "")
        response = response.replace("S>", "")

        return response

    def _handler_command_init_logging(self, *args, **kwargs):

        log.debug("%%% in _handler_command_init_logging")

        next_state = None
        next_agent_state = None
        result = None

        kwargs['expected_prompt'] = "S>"
        log.debug("WANT " + repr(kwargs['expected_prompt']))
        result = self._do_cmd_resp(InstrumentCmds.INIT_LOGGING, *args, **kwargs)

        return (next_state, (next_agent_state, result))
        #return (next_state, result)

    def _parse_init_logging_response(self, response, prompt):
        """
        Parse handler for init_logging command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """
        log.debug("_parse_init_logging_response response = " + repr(response))
        log.debug("_parse_init_logging_response prompt = " + repr(prompt))

        #'InitLogging\r\n<WARNING>\r\nSample number will reset\r\nAll recorded data will be lost\r\n</WARNING>\r\n<ConfirmationRequired/>\r\n<Executed/>\r\nS>'

        if prompt != 'S>':
            raise InstrumentProtocolException('Initlogging command not recognized: %s' % response)

        if "ConfirmationRequired" in response:
            log.debug("_parse_init_logging_response - ConfirmationRequired, RE-ISSUEING command")

            # clear out the last command.
            self._promptbuf = ''
            self._linebuf = ''

            self._do_cmd_direct(InstrumentCmds.INIT_LOGGING + NEWLINE)
            (prompt, response) = self._get_response(timeout=30)
            log.debug("_parse_init_logging_response RESULT = " + repr(response))
            log.debug("_parse_init_logging_response prompt = " + repr(prompt))
            if (Prompt.COMMAND == prompt and
                'InitLogging\r\n<Executed/>\r\nS>' == response):
                return True

        return False

    def _handler_command_clock_sync(self, *args, **kwargs):
        """
        execute a clock sync on the leading edge of a second change
        @retval (next_state, result) tuple, (None, (None, )) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None

        timeout = kwargs.get('timeout', TIMEOUT)
        self._sync_clock(InstrumentCmds.SET_TIME, Parameter.TIME, timeout, time_format="%Y-%m-%dT%H:%M:%S")

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
            self._stop_logging()

            # Sync the clock
            timeout = kwargs.get('timeout', TIMEOUT)
            self._sync_clock(InstrumentCmds.SET_TIME, Parameter.TIME, timeout, time_format="%Y-%m-%dT%H:%M:%S")

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging()

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
        self._do_cmd_resp(InstrumentCmds.SET, Parameter.TIME, get_timestamp_delayed("%Y-%m-%dT%H:%M:%S"), **kwargs)

        next_state = None
        result = None

        # Issue start command and switch to autosample if successful.
        self._do_cmd_no_resp(InstrumentCmds.START_LOGGING, *args, **kwargs)

        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return (next_state, (next_agent_state, result))

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """

        log.debug("%%% IN _handler_autosample_stop_autosample")

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

        log.debug("%%% IN _handler_autosample_exit")

        pass

    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """
        log.debug("IN _handler_direct_access_enter")
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._sent_cmds = []


    def _handler_direct_access_execute_direct(self, data):
        """
        """
        log.debug("IN _handler_direct_access_execute_direct")
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

        log.debug("IN _handler_direct_access_stop_direct")

        next_state = None
        result = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        log.debug("%%% IN _handler_direct_access_exit")
        pass

    ########################################################################
    # Private helpers.
    ########################################################################

    def _is_logging(self, timeout=TIMEOUT):
        """
        Wake up the instrument and inspect the prompt to determine if we
        are in streaming
        @param: timeout - Command timeout
        @return: True - instrument logging, False - not logging,
                 None - unknown logging state
        @raise: InstrumentProtocolException if we can't identify the prompt
        """
        prompt = self._wakeup(timeout=timeout, delay=0.1)
        log.debug("Prompt return: %s" % prompt)
        if  Prompt.AUTOSAMPLE == prompt:
            log.debug("Instrument state: logging")
            return True
        elif Prompt.COMMAND == prompt:
            log.debug("Instrument state: command")
            return False
        else:
            raise InstrumentProtocolException("Unknown prompt '%s'" % prompt)

    def _start_logging(self, timeout=TIMEOUT):
        """
        Command the instrument to start logging
        @param timeout: how long to wait for a prompt
        @return: True if successful
        @raise: InstrumentProtocolException if failed to start logging
        """
        log.debug("Start Logging!")
        if(self._is_logging()):
            return True

        self._do_cmd_no_resp(InstrumentCmds.START_LOGGING, timeout=timeout)

        if not self._is_logging(timeout):
            raise InstrumentProtocolException("failed to start logging")

        return True

    def _stop_logging(self, timeout=TIMEOUT):
        """
        Command the instrument to stop logging
        @param timeout: how long to wait for a prompt
        @return: True if successful
        @raise: InstrumentTimeoutException if prompt isn't seen
        @raise: InstrumentProtocolException failed to stop logging
        """
        log.debug("Stop Logging!")

        if not self._is_logging():
            return True

        # Issue the stop command.
        self._do_cmd_resp(InstrumentCmds.STOP_LOGGING)

        if self._is_logging(timeout):
            raise InstrumentProtocolException("failed to stop logging")

        return True


    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        log.debug("sbe54 _set_params start")

        startup = False
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        try:
            startup = args[1]
        except IndexError:
            pass

        self._verify_not_readonly(*args, **kwargs)

        for (key, val) in params.iteritems():
            log.debug("KEY = " + str(key) + " VALUE = " + str(val))
            result = self._do_cmd_resp(InstrumentCmds.SET, key, val, **kwargs)

        log.debug("sbe54 _set_params update_params")
        self._update_params()
        log.debug("sbe54 _set_params complete")

    def _build_set_command(self, cmd, param, val):
        """
        Build handler for set commands. SETparam=val followed by newline.
        String val constructed by param dict formatting function.  <--- needs a better/clearer way
        @param param the parameter key to set.
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        @ retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        try:
            str_val = self._param_dict.format(param, val)
            if None == str_val:
                raise InstrumentParameterException("Driver PARAM was None!!!!")
            set_cmd = 'set%s=%s' % (param, str_val)
            set_cmd = set_cmd + NEWLINE
            log.debug("set_cmd = " + repr(set_cmd))
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return set_cmd

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name="acquire status")
        self._cmd_dict.add(Capability.CLOCK_SYNC, display_name="sync clock")
        self._cmd_dict.add(Capability.GET_CONFIGURATION_DATA, display_name="get configuration data")
        self._cmd_dict.add(Capability.GET_EVENT_COUNTER, display_name="get event counter")
        self._cmd_dict.add(Capability.GET_HARDWARE_DATA, display_name="get hardware data")
        self._cmd_dict.add(Capability.GET_STATUS_DATA, display_name="get status data")
        self._cmd_dict.add(Capability.SAMPLE_REFERENCE_OSCILLATOR, display_name="sample reference oscillator")
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="start autosample")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="stop autosample")
        self._cmd_dict.add(Capability.TEST_EEPROM, display_name="test eeprom")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        log.debug("%%% IN _build_param_dict")
        # THIS wants to take advantage of the particle code,
        # as the particles handle parsing the fields out
        # no sense doing it again here

        #
        # StatusData
        #
        self._param_dict.add(Parameter.TIME,
            SBE54tpsStatusDataParticle.LINE2,
            lambda match : match.group(1),
            str,
            type=ParameterDictType.STRING,
            expiration=0,
            visibility=ParameterDictVisibility.READ_ONLY,
            display_name="instrument time"
        )

        self._param_dict.add(Parameter.SAMPLE_PERIOD,
                             SBE54tpsConfigurationDataParticle.LINE28,
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="sample period",
                             default_value=15,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.BATTERY_TYPE,
                             SBE54tpsConfigurationDataParticle.LINE24,
                             lambda match : int(match.group(1)),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="battery type",
                             default_value=1,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True)

        self._param_dict.add(Parameter.ENABLE_ALERTS,
                             SBE54tpsConfigurationDataParticle.LINE26,
                             lambda match : bool(int(match.group(1))),
                             self._bool_to_int_string,
                             type=ParameterDictType.BOOL,
                             display_name="enable alerts",
                             default_value=1,
                             visibility=ParameterDictVisibility.IMMUTABLE,
                             startup_param=True,
                             direct_access=True)

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        # This instrument will automatically put itself back into autosample mode after a couple minutes idle
        # in command mode.  So if we see a sample we need to figure out if we need to raise an event to adjust
        # the state machine.
        if(self._extract_sample(SBE54tpsSampleDataParticle, SAMPLE_DATA_REGEX_MATCHER, chunk, timestamp)):
            log.debug("Sample record detected, publish a sample")
            if(self._protocol_fsm.get_current_state() == ProtocolState.COMMAND):
                log.debug("FSM appears out of date.  Fixing it!")
                self._protocol_fsm.on_event(ProtocolEvent.RECOVER_AUTOSAMPLE)
            return

        if(self._extract_sample(SBE54tpsStatusDataParticle, STATUS_DATA_REGEX_MATCHER, chunk, timestamp)) : return
        if(self._extract_sample(SBE54tpsConfigurationDataParticle, CONFIGURATION_DATA_REGEX_MATCHER, chunk, timestamp)) : return
        if(self._extract_sample(SBE54tpsEventCounterDataParticle, EVENT_COUNTER_DATA_REGEX_MATCHER, chunk, timestamp)) : return
        if(self._extract_sample(SBE54tpsHardwareDataParticle, HARDWARE_DATA_REGEX_MATCHER, chunk, timestamp)) : return
        if(self._extract_sample(SBE54tpsSampleRefOscDataParticle, SAMPLE_REF_OSC_MATCHER, chunk, timestamp)) : return

    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the sbe26plus device.
        """
        log.debug("%%% IN _send_wakeup")
        self._connection.send(NEWLINE)

    def _build_simple_command(self, cmd):
        """
        Build handler for basic sbe26plus commands.
        @param cmd the simple sbe37 command to format.
        @retval The command to be sent to the device.
        """
        log.debug("%%% IN _build_simple_command")
        return cmd + NEWLINE

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Wake the device then issue
        display status and display calibration commands. The parameter
        dict will match line output and udpate itself.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        log.debug("start _update_params")
        # Get old param dict config.
        old_config = self._param_dict.get_config()

        # Issue display commands and parse results.
        timeout = kwargs.get('timeout', TIMEOUT)

        log.debug("Run status command: %s" % InstrumentCmds.GET_STATUS_DATA)
        response = self._do_cmd_resp(InstrumentCmds.GET_STATUS_DATA, timeout=timeout)
        for line in response.split(NEWLINE):
            self._param_dict.update(line)
        log.debug("status command response: %s" % response)

        log.debug("Run configure command: %s" % InstrumentCmds.GET_CONFIGURATION_DATA)
        response = self._do_cmd_resp(InstrumentCmds.GET_CONFIGURATION_DATA, timeout=timeout)
        for line in response.split(NEWLINE):
            self._param_dict.update(line)
        log.debug("configure command response: %s" % response)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        log.debug("new_config: %s == old_config: %s" % (new_config, old_config))
        if not dict_equal(old_config, new_config, ignore_keys=Parameter.TIME):
            log.debug("configuration has changed.  Send driver event")
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    #
    # Many of these will want to rise up to base class if not there already
    #
    @staticmethod
    def _int_to_string(v):
        """
        Write an int value to string formatted for sbe37 set operations.
        @param v An int val.
        @retval an int string formatted for sbe37 set operations.
        @throws InstrumentParameterException if value not an int.
        """
        log.debug("IN _int_to_string")

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
        log.debug("IN _float_to_string")

        if not isinstance(v, float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            #return '%e' % v #This returns a exponential formatted float
            # every time. not what is needed
            return str(v) #return a simple float

    @staticmethod
    def _bool_to_int_string(v):
        # return a string of an into of 1 or 0 to indicate true/false

        if True == v:
            return "1"
        elif False == v:
            return "0"
        else:
            return None

