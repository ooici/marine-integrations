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
from mi.core.time import get_timestamp_delayed

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.log import get_logger ; log = get_logger()


from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException

from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue
from mi.core.instrument.chunker import StringChunker
from pyon.agent.agent import ResourceAgentState
# newline.
NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 10

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


# Packet config
STREAM_NAME_PARSED = DataParticleValue.PARSED
STREAM_NAME_RAW = DataParticleValue.RAW
PACKET_CONFIG = [STREAM_NAME_PARSED, STREAM_NAME_RAW]

PACKET_CONFIG = {
    STREAM_NAME_PARSED : 'ctd_parsed_param_dict',
    STREAM_NAME_RAW : 'ctd_raw_param_dict'
}



# Device specific parameters.
class InstrumentCmds(BaseEnum):
    """
    Instrument Commands
    These are the commands that according to the science profile must be supported.
    """


    #### Artificial Constructed Commands for Driver ####
    SET = "set"  # need to bring over _build_set_command/_parse_set_response

    ################
    #### Status ####
    ################
    GET_CONFIGURATION_DATA = "GetCD"
    GET_STATUS_DATA = "GetSD"
    GET_EVENT_COUNTER_DATA = "GetEC"
    GET_HARDWARE_DATA = "GetHD"

    ###############################
    #### Setup - Communication ####
    ###############################
    # SET_BAUD_RATE = "SetBaudRate"                                         # DO NOT IMPLEMENT

    #########################
    #### Setup - General ####
    #########################
    # INITIALIZE = "*Init"                                                  # DO NOT IMPLEMENT
    SET_SAMPLE_PERIOD = "SetSamplePeriod"                  # VARIABLE
    SET_TIME = "SetTime"                                   # VARIABLE       # S>settime=2006-01-15T13:31:00
    SET_BATTERY_TYPE = "SetBatteryType"                    # VARIABLE

    ###########################
    #### Setup Data Output ####
    ###########################
    SET_ENABLE_ALERTS = "SetEnableAlerts"                   # VARIABLE

    ##################
    #### Sampling ####
    ##################
    INIT_LOGGING = "InitLogging"
    START_LOGGING = "Start"
    STOP_LOGGING = "Stop"
    SAMPLE_REFERENCE_OSCILLATOR = "SampleRefOsc"

    ################################
    #### Data Access and Upload ####
    ################################
    # GET_SAMPLES = "GetSamples"                                            # DO NOT IMPLEMENT
    # GET_LAST_PRESSURE_SAMPLES = "GetLastPSamples"                         # DO NOT IMPLEMENT
    # GET_LAST_REFERENCE_SAMPLES = "GetLastRSamples"                        # DO NOT IMPLEMENT
    # GET_REFERENCE_SAMPLES_LIST = "GetRSampleList"                         # DO NOT IMPLEMENT
    SET_UPLOAD_TYPE = "SetUploadType"                      # VARIABLE
    # UPLOAD_DATA = "UploadData"                                            # DO NOT IMPLEMENT

    ####################
    #### Diagnostic ####
    ####################
    RESET_EC = "ResetEC"
    TEST_EEPROM = "TestEeprom"
    # TEST_REFERENCE_OSCILLATOR = "TestRefOsc"                              # DO NOT IMPLEMENT

    ##################################
    #### Calibration Coefficients ####
    ##################################
    # SetAcqOscCalDate=S        S= acquisition crystal calibration date.
    # SET_ACQUISITION_OSCILLATOR_CALIBRATION_DATE = "SetAcqOscCalDate"      # DO NOT IMPLEMENT

    # SetFRA0=F                 F= acquisition crystal frequency A0.
    # SET_ACQUISITION_FREQUENCY_A0 = "SetFRA0"                              # DO NOT IMPLEMENT

    # SetFRA1=F                 F= acquisition crystal frequency A1.
    # SET_ACQUISITION_FREQUENCY_A1 = "SetFRA1"                              # DO NOT IMPLEMENT

    # SetFRA2=F                 F= acquisition crystal frequency A2.
    # SET_ACQUISITION_FREQUENCY_A2 = "SetFRA2"                              # DO NOT IMPLEMENT

    # SetFRA3=F                 F= acquisition crystal frequency A3.
    # SET_ACQUISITION_FREQUENCY_A3 = "SetFRA3"                              # DO NOT IMPLEMENT

    # SetPressureCalDate=S      S= pressure sensor calibration date.
    # SET_PRESSURE_CALIBRATION_DATE = "SetPressureCalDate"                  # DO NOT IMPLEMENT

    # SetPressureSerialNum=S    S= pressure sensor serial number.
    # SET_PRESSURE_SERIAL_NUMBER = "SetPressureSerialNum"                   # DO NOT IMPLEMENT

    # SetPRange=F               F= pressure sensor full scale range (psia).
    # SET_PRESSURE_SENSOR_FULL_SCALE_RANGE = "SetPRange"                    # DO NOT IMPLEMENT

    # SetPOffset=F              F= pressure sensor offset (psia).
    # SET_PRESSURE_SENSOR_OFFSET = "SetPOffset"                             # DO NOT IMPLEMENT

    # SetPU0=F                  F= pressure sensor U0.
    # SET_PRESSURE_SENSOR_U0 = "SetPU0"                                     # DO NOT IMPLEMENT

    # SetPY1=F                  F= pressure sensor Y1.
    # SET_PRESSURE_SENSOR_Y1 = "SetPY1"                                     # DO NOT IMPLEMENT

    # SetPY2=F                  F= pressure sensor Y2.
    # SET_PRESSURE_SENSOR_Y2 = "SetPY2"                                     # DO NOT IMPLEMENT

    # SetPY3=F                  F= pressure sensor Y3.
    # SET_PRESSURE_SENSOR_Y3 = "SetPY3"                                     # DO NOT IMPLEMENT

    # SetPC1=F                  F= pressure sensor C1.
    # SET_PRESSURE_SENSOR_C1 = "SetPC1"                                     # DO NOT IMPLEMENT

    # SetPC2=F                  F= pressure sensor C2.
    # SET_PRESSURE_SENSOR_C2 = "SetPC2"                                     # DO NOT IMPLEMENT

    # SetPC3=F                  F= pressure sensor C3.
    # SET_PRESSURE_SENSOR_C3 = "SetPC3"                                     # DO NOT IMPLEMENT

    # SetPD1=F                  F= pressure sensor D1.
    # SET_PRESSURE_SENSOR_D1 = "SetPD1"                                     # DO NOT IMPLEMENT

    # SetPD2=F                  F= pressure sensor D2.
    # SET_PRESSURE_SENSOR_D2 = "SetPD2"                                     # DO NOT IMPLEMENT

    # SetPT1=F                  F= pressure sensor T1.
    # SET_PRESSURE_SENSOR_T1 = "SetPT1"                                     # DO NOT IMPLEMENT

    # SetPT2=F                  F= pressure sensor T2.
    # SET_PRESSURE_SENSOR_T2 = "SetPT2"                                     # DO NOT IMPLEMENT

    # SetPT3=F                  F= pressure sensor T3.
    # SET_PRESSURE_SENSOR_T3 = "SetPT3"                                     # DO NOT IMPLEMENT

    # SetPT4=F                  F= pressure sensor T4.
    # SET_PRESSURE_SENSOR_T4 = "SetPT4"                                     # DO NOT IMPLEMENT



class ProtocolState(BaseEnum):
    """
    Protocol states
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    #TEST = DriverProtocolState.TEST
    #CALIBRATE = DriverProtocolState.CALIBRATE

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """

    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    # Do we need these here?
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER

    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE

    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    FORCE_STATE = DriverEvent.FORCE_STATE

    INIT_LOGGING = 'PROTOCOL_EVENT_INIT_LOGGING'
    SAMPLE_REFERENCE_OSCILLATOR = 'PROTOCOL_EVENT_SAMPLE_REFERENCE_OSCILLATOR'
    TEST_EEPROM = 'PROTOCOL_EVENT_TEST_EEPROM'
    RESET_EC = 'PROTOCOL_EVENT_RESET_EC'
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    PING_DRIVER = DriverEvent.PING_DRIVER

    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    #ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
    ACQUIRE_STATUS  = ProtocolEvent.ACQUIRE_STATUS
    INIT_LOGGING = ProtocolEvent.INIT_LOGGING
    SAMPLE_REFERENCE_OSCILLATOR = ProtocolEvent.SAMPLE_REFERENCE_OSCILLATOR
    TEST_EEPROM = ProtocolEvent.TEST_EEPROM
    RESET_EC = ProtocolEvent.RESET_EC

# Device specific parameters.
class Parameter(DriverParameter):
    """
    Device parameters
    """
    #
    # Common fields in all commands
    #

    DEVICE_TYPE = "device_type"  #str
    SERIAL_NUMBER = "serial_number" #str (could be int...)

    #
    # StatusData
    #

    TIME = "time" # str
    EVENT_COUNT = "event_count" #int
    MAIN_SUPPLY_VOLTAGE = "main_supply_voltage" # float
    NUMBER_OF_SAMPLES = "number_of_samples" # int
    BYTES_USED = "bytes_used" # int
    BYTES_FREE = "bytes_free" # int

    #
    # ConfigurationData
    #

    ACQ_OSC_CAL_DATE = "acq_osc_cal_date" # date
    FRA0 = "acquisition_frequency_a0" # float
    FRA1 = "acquisition_frequency_a1" # float
    FRA2 = "acquisition_frequency_a2" # float
    FRA3 = "acquisition_frequency_a3" # float
    PRESSURE_SERIAL_NUM = "pressure_serial_num" # string
    PRESSURE_CAL_DATE = "pressure_cal_date" # date
    PU0 = "pressure_sensor_u0" # float
    PY1 = "pressure_sensor_y1" # float
    PY2 = "pressure_sensor_y2" # float
    PY3 = "pressure_sensor_y3" # float
    PC1 = "pressure_sensor_c1" # float
    PC2 = "pressure_sensor_c2" # float
    PC3 = "pressure_sensor_c3" # float
    PD1 = "pressure_sensor_d1" # float
    PD2 = "pressure_sensor_d2" # float
    PT1 = "pressure_sensor_t1" # float
    PT2 = "pressure_sensor_t2" # float
    PT3 = "pressure_sensor_t3" # float
    PT4 = "pressure_sensor_t4" # float
    PRESSURE_OFFSET = "pressure_offset" # float (psia)
    PRESSURE_RANGE = "pressure_range" # float (psia)
    BATTERY_TYPE = "batterytype" # int
    BAUD_RATE = "baudrate" # int
    ENABLE_ALERTS = "enablealerts" # bool
    UPLOAD_TYPE = "uploadtype" # int
    SAMPLE_PERIOD = "sampleperiod" # int

    #
    # Event Counter
    #

    NUMBER_EVENTS = "number_events" # int
    MAX_STACK = "max_stack" # int
    POWER_ON_RESET = "power_on_reset" # int
    POWER_FAIL_RESET = "power_fail_reset" # int
    SERIAL_BYTE_ERROR = "serial_byte_error" # int
    COMMAND_BUFFER_OVERFLOW = "command_buffer_overflow" # int
    SERIAL_RECEIVE_OVERFLOW = "serial_receive_overflow" # int
    LOW_BATTERY = "low_battery" # int
    SIGNAL_ERROR = "signal_error" # int
    ERROR_10 = "error_10" # int
    ERROR_12 = "error_12" # int

    #
    # Hardware Data
    #

    MANUFACTURER = "manufacturer" # string
    FIRMWARE_VERSION = "firmware_version" # string
    FIRMWARE_DATE = "firmware_date" # date
    HARDWARE_VERSION = "hardware_version" # string
    PCB_SERIAL_NUMBER = "pcb_serial_number" # string
    PCB_TYPE = "pcb_type" # string
    MANUFACTUR_DATE = "manufactur_date" # date

# Device prompts.
class Prompt(BaseEnum):
    """
    io prompts.
    """
    COMMAND = "<Executed/>\r\nS>"

    AUTOSAMPLE = "<Executed/>\r\n"

    BAD_COMMAND_AUTOSAMPLE = "<Error.*?\r\n<Executed/>\r\n" # REGEX ALERT
    BAD_COMMAND = "<Error.*?\r\n<Executed/>\r\nS>" # REGEX ALERT


######################################### PARTICLES #############################


class SBE54tpsStatusDataParticleKey(BaseEnum):
    DEVICE_TYPE = "device_type"
    SERIAL_NUMBER = "serial_number"
    TIME = "time"
    EVENT_COUNT = "event_count"
    MAIN_SUPPLY_VOLTAGE = "main_supply_voltage"
    NUMBER_OF_SAMPLES = "number_of_samples"
    BYTES_USED = "bytes_used"
    BYTES_FREE = "bytes_free"

class SBE54tpsStatusDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """

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
                            SBE54tpsStatusDataParticleKey.TIME
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
                            #SBE54tpsStatusDataParticleKey.TIME
                        ]:
                            # 2012-11-13T17:56:42
                            # yyyy-mm-ddThh:mm:ss

                            '''
                            log.debug("GOT TIME FROM INSTRUMENT = " + str(val))
                            text_timestamp = val
                            py_timestamp = time.strptime(text_timestamp, "%Y-%m-%dT%H:%M:%S")
                            timestamp = ntplib.system_to_ntp_time(time.mktime(py_timestamp))
                            log.debug("CONVERTED TIME FROM INSTRUMENT = " + str(timestamp))
                            single_var_matches[key] = timestamp
                            '''

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
    ACQ_OSC_CAL_DATE = "acquisition_crystal_calibration_date"
    FRA0 = "fra0"
    FRA1 = "fra1"
    FRA2 = "fra2"
    FRA3 = "fra3"
    PRESSURE_SERIAL_NUM = "pressure_serial_number"
    PRESSURE_CAL_DATE = "pressure_calibration_date"
    PU0 = "pu0"
    PY1 = "py1"
    PY2 = "py2"
    PY3 = "py3"
    PC1 = "pc1"
    PC2 = "pc2"
    PC3 = "pc3"
    PD1 = "pd1"
    PD2 = "pd2"
    PT1 = "pt1"
    PT2 = "pt2"
    PT3 = "pt3"
    PT4 = "pt4"
    PRESSURE_OFFSET = "pressure_sensor_offset" # pisa
    PRESSURE_RANGE = "pressure_sensor_full_scale_range" # pisa
    BATTERY_TYPE = "battery_type"
    BAUD_RATE = "baud_rate"
    ENABLE_ALERTS = "enable_alerts"
    UPLOAD_TYPE = "upload_type"
    SAMPLE_PERIOD = "sample_period"

class SBE54tpsConfigurationDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
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
                            SBE54tpsConfigurationDataParticleKey.PRESSURE_SERIAL_NUM,
                        ]:
                            single_var_matches[key] = val

                        # int
                        elif key in [
                            SBE54tpsConfigurationDataParticleKey.SERIAL_NUMBER,
                            SBE54tpsConfigurationDataParticleKey.BATTERY_TYPE,
                            SBE54tpsConfigurationDataParticleKey.UPLOAD_TYPE,
                            SBE54tpsConfigurationDataParticleKey.SAMPLE_PERIOD,
                            SBE54tpsConfigurationDataParticleKey.BAUD_RATE
                        ]:
                            single_var_matches[key] = int(val)


                        # int
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

                        # date
                        elif key in [
                            SBE54tpsConfigurationDataParticleKey.ACQ_OSC_CAL_DATE,
                            SBE54tpsConfigurationDataParticleKey.PRESSURE_CAL_DATE
                        ]:
                            # ISO8601-2000 format.
                            # yyyy-mm-dd
                            # 2007-03-01
                            text_timestamp = val
                            py_timestamp = time.strptime(text_timestamp, "%Y-%m-%d")
                            timestamp = ntplib.system_to_ntp_time(time.mktime(py_timestamp))
                            single_var_matches[key] = timestamp

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

    LINE1 = r"EventSummary numEvents='(\d+)' maxStack='(\d+)'/>"
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
                        log.debug("KEY [" + str(key) + "] = VAL [" + str(val) +"]")
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
            log.debug("SETTING " + str(key) + " = " + str(value))
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
    MANUFACTUR_DATE = "manufactur_date"

class SBE54tpsHardwareDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """

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
                            SBE54tpsHardwareDataParticleKey.HARDWARE_VERSION,
                            SBE54tpsHardwareDataParticleKey.PCB_SERIAL_NUMBER,
                            SBE54tpsHardwareDataParticleKey.PCB_TYPE
                        ]:
                            single_var_matches[key] = val

                        # int
                        elif key in [
                            SBE54tpsHardwareDataParticleKey.SERIAL_NUMBER
                        ]:
                            single_var_matches[key] = int(val)

                        # date
                        elif key in [
                            SBE54tpsHardwareDataParticleKey.FIRMWARE_DATE,
                            SBE54tpsHardwareDataParticleKey.MANUFACTUR_DATE
                        ]:
                            # <FirmwareDate>Mar 22 2007</FirmwareDate>
                            # <MfgDate>Jun 27 2007</MfgDate>
                            text_timestamp = val
                            py_timestamp = time.strptime(text_timestamp, "%b %d %Y")
                            timestamp = ntplib.system_to_ntp_time(time.mktime(py_timestamp))
                            single_var_matches[key] = timestamp

                        else:
                            raise SampleException("Unknown variable type in SBE54tpsConfigurationDataParticle._build_parsed_values")

        result = []
        for (key, value) in single_var_matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result

class SBE54tpsSampleDataParticleKey(BaseEnum):
    SAMPLE_NUMBER = "sample_number"
    SAMPLE_TYPE = "sample_type"
    INST_TIME = "InstTime" # FUTURE "inst_time"
    PRESSURE = "pressure" # psi
    PRESSURE_TEMP = "pressure_temp"

class SBE54tpsSampleDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """

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
                            log.debug("SAMPLE_TYPE = " + val)
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
    SET_TIMEOUT = "SetTimeout"
    SET_TIMEOUT_MAX = "SetTimeoutMax"
    SET_TIMEOUT_ICD = "SetTimeoutICD"
    SAMPLE_NUMBER = "sample_number"
    SAMPLE_TYPE = "sample_type"
    SAMPLE_TIMESTAMP = "sample_timestamp"
    REF_OSC_FREQ = "ref_osc_freq"
    PCB_TEMP_RAW = "pcb_temp_raw"
    REF_ERROR_PPM = "ref_error_ppm"

class SBE54tpsSampleRefOscDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
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

                        # str
                        if key in [
                            SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TYPE
                        ]:
                            log.debug("SAMPLE_TYPE = " + val)
                            single_var_matches[key] = val

                        # int
                        elif key in [
                            SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT,
                            SBE54tpsSampleRefOscDataParticleKey.SAMPLE_NUMBER,
                            SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_MAX,
                            SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_ICD,
                            SBE54tpsSampleRefOscDataParticleKey.PCB_TEMP_RAW,
                        ]:
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

######################################### /PARTICLES #############################


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
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER,                  self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT,                   self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER,               self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.FORCE_STATE,            self._handler_unknown_force_state)   ######
        #self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.START_DIRECT,           self._handler_command_start_direct)  ##???? from unknown state?


        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.FORCE_STATE,            self._handler_unknown_force_state)   ######

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER,                  self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT,                   self._handler_command_exit)
        # have NO TAKE SAMPLE COMMAND
        #self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE,         self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE,       self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET,                    self._handler_command_get)  ### ??
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET,                    self._handler_command_set)  ### ??
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.INIT_LOGGING,           self._handler_command_init_logging)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC,             self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS,         self._handler_command_aquire_status)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT,           self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SAMPLE_REFERENCE_OSCILLATOR, self._handler_sample_ref_osc)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.TEST_EEPROM,            self._handler_command_test_eeprom)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.RESET_EC,               self._handler_command_reset_ec)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER,               self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT,                self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET,                 self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE,     self._handler_autosample_stop_autosample)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER,            self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT,             self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT,   self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT,      self._handler_direct_access_stop_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCmds.SET,                    self._build_set_command)
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

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)



    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        return_list = []

        sieve_matchers = [STATUS_DATA_REGEX_MATCHER,
                          CONFIGURATION_DATA_REGEX_MATCHER,
                          EVENT_COUNTER_DATA_REGEX_MATCHER,
                          HARDWARE_DATA_REGEX_MATCHER,
                          SAMPLE_DATA_REGEX_MATCHER,
                          SAMPLE_REF_OSC_MATCHER]



        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        @TODO CANDIDATE FOR PROMOTING TO BASE CLASS.
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
        if ((prompt != Prompt.COMMAND) or ('Error' in response)):
            raise InstrumentProtocolException('Protocol._parse_set_response : Set command not recognized: %s' % response)

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
        log.debug("%%% IN _handler_unknown_discover NEED TO WRITE THIS METHOD.....")

        next_state = None
        next_agent_state = None

        current_state = self._protocol_fsm.get_current_state()

        if current_state == ProtocolState.AUTOSAMPLE:
            next_agent_state = ResourceAgentState.STREAMING
        # If I think I am in COMMAND state, I better verify that.
        elif (ProtocolState.COMMAND == current_state or
             ProtocolState.UNKNOWN == current_state):
            delay = 0.5
            prompt = self._wakeup(timeout=timeout, delay=delay) # '<Executed/>\r\n'
            log.debug("_handler_unknown_discover in UNKNOWN got prompt " + repr(prompt))
            if  Prompt.AUTOSAMPLE  == prompt:
                next_state = ProtocolState.AUTOSAMPLE
                next_agent_state = ResourceAgentState.STREAMING
            elif Prompt.COMMAND  == prompt:
                next_state = ProtocolState.COMMAND
                next_agent_state = ResourceAgentState.IDLE

            self._do_cmd_resp(InstrumentCmds.GET_CONFIGURATION_DATA, timeout=timeout)
            self._do_cmd_resp(InstrumentCmds.GET_STATUS_DATA, timeout=timeout)
            self._do_cmd_resp(InstrumentCmds.GET_EVENT_COUNTER_DATA, timeout=timeout)
            self._do_cmd_resp(InstrumentCmds.GET_HARDWARE_DATA, timeout=timeout)

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

    def _handler_command_aquire_status(self, *args, **kwargs):
        """
        Send a command
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
        #return (next_state, result)
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

    def _handler_command_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @throws InstrumentParameterException if missing or invalid parameter.
        """

        log.debug("%%% IN _handler_command_get")

        next_state = None
        result = None

        # Retrieve the required parameter, raise if not present.
        try:
            params = args[0]

        except IndexError:
            raise InstrumentParameterException('Get command requires a parameter list or tuple.')


        log.debug("params = " + repr(params))


        # If all params requested, retrieve config.
        if params == DriverParameter.ALL:
            result = self._param_dict.get_config()
            # If all params requested, retrieve config.
        elif params == [DriverParameter.ALL]:
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

        log.debug("%%% IN _handler_command_set")

        next_state = None
        result = None

        try:
            params = args[0]
            log.debug("######### params = " + str(repr(params)))

        except IndexError:
            raise InstrumentParameterException('_handler_command_set Set command requires a parameter dict.')

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        else:
            for (key, val) in params.iteritems():
                log.debug("KEY = " + str(key) + " VALUE = " + str(val))
                result = self._do_cmd_resp(InstrumentCmds.SET, key, val, **kwargs)
                log.debug("**********************RESULT************* = " + str(result))
                self._update_params()

        return (next_state, result)

    def _handler_command_clock_sync(self, *args, **kwargs):
        """
        execute a clock sync on the leading edge of a second change
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        log.debug("%%% IN _handler_command_clock_sync")

        next_state = None
        next_agent_state = None
        result = None

        timeout = kwargs.get('timeout', TIMEOUT)
        delay = 1
        prompt = self._wakeup(timeout=timeout, delay=delay)

        # lets clear out any past data so it doesnt confuse the command
        self._linebuf = ''
        self._promptbuf = ''

        """
        SetTime=x
        settime=2012-11-13T15:23:18

        ---
        Trying it a bit different from the sbe26
        ---
        """

        timestamp = get_timestamp_delayed("%Y-%m-%dT%H:%M:%S")
        set_cmd = '%s=%s' % (InstrumentCmds.SET_TIME, timestamp) + NEWLINE

        self._do_cmd_direct(set_cmd)
        (prompt, response) = self._get_response() #timeout=30)

        if response != set_cmd + Prompt.COMMAND:
            raise InstrumentProtocolException("_handler_clock_sync - response != set_cmd")

        if prompt != Prompt.COMMAND:
            raise InstrumentProtocolException("_handler_clock_sync - prompt != Prompt.COMMAND")

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

        log.debug("%%% IN _build_set_command")

        """
        This breaks startup params

        if param not in [
            Parameter.TIME,
            Parameter.UPLOAD_TYPE,
            Parameter.ENABLE_ALERTS,
            Parameter.SAMPLE_PERIOD,
        ]:
            raise InstrumentParameterException("Parameter " +str(param) + " is not allowed to be set")
        """

        try:
            log.debug("PARAM = "+ repr(param))
            log.debug("VAL = "+ repr(val))
            str_val = self._param_dict.format(param, val)
            if None == str_val:
                raise InstrumentParameterException("Driver PARAM was None!!!!")
            set_cmd = 'set%s=%s' % (param, str_val)
            set_cmd = set_cmd + NEWLINE
            log.debug("set_cmd = " + repr(set_cmd))
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return set_cmd

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

        self._param_dict.add(Parameter.DEVICE_TYPE,
            SBE54tpsStatusDataParticle.LINE1,
            lambda match : int(match.group(1)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.SERIAL_NUMBER,
            SBE54tpsStatusDataParticle.LINE1,
            lambda match : int(match.group(2)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.TIME,
            SBE54tpsStatusDataParticle.LINE2,
            lambda match : match.group(1), # self._string_to_datetime(match.group(1)),
            self._string_to_string)
            #self._time_to_string)

        self._param_dict.add(Parameter.EVENT_COUNT,
            SBE54tpsStatusDataParticle.LINE3,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.MAIN_SUPPLY_VOLTAGE,
            SBE54tpsStatusDataParticle.LINE4,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.NUMBER_OF_SAMPLES,
            SBE54tpsStatusDataParticle.LINE5,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.BYTES_USED,
            SBE54tpsStatusDataParticle.LINE6,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.BYTES_FREE,
            SBE54tpsStatusDataParticle.LINE7,
            lambda match :int(match.group(1)),
            self._int_to_string)

        #
        # ConfigurationData
        #

        self._param_dict.add(Parameter.DEVICE_TYPE,
            SBE54tpsConfigurationDataParticle.LINE1,
            lambda match : int(match.group(1)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.SERIAL_NUMBER,
            SBE54tpsConfigurationDataParticle.LINE1,
            lambda match : int(match.group(2)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.ACQ_OSC_CAL_DATE,
            SBE54tpsConfigurationDataParticle.LINE2,
            lambda match : self._string_month_number_to_date(match.group(1)),
            self._date_to_string)

        self._param_dict.add(Parameter.FRA0,
            SBE54tpsConfigurationDataParticle.LINE3,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.FRA1,
            SBE54tpsConfigurationDataParticle.LINE4,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.FRA2,
            SBE54tpsConfigurationDataParticle.LINE5,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.FRA3,
            SBE54tpsConfigurationDataParticle.LINE6,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PRESSURE_SERIAL_NUM,
            SBE54tpsConfigurationDataParticle.LINE7,
            lambda match : string.upper(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.PRESSURE_CAL_DATE,
            SBE54tpsConfigurationDataParticle.LINE8,
            lambda match : self._string_month_number_to_date(match.group(1)),
            self._date_to_string)

        self._param_dict.add(Parameter.PU0,
            SBE54tpsConfigurationDataParticle.LINE9,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PY1,
            SBE54tpsConfigurationDataParticle.LINE10,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PY2,
            SBE54tpsConfigurationDataParticle.LINE11,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PY3,
            SBE54tpsConfigurationDataParticle.LINE12,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PC1,
            SBE54tpsConfigurationDataParticle.LINE13,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PC2,
            SBE54tpsConfigurationDataParticle.LINE14,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PC3,
            SBE54tpsConfigurationDataParticle.LINE15,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PD1,
            SBE54tpsConfigurationDataParticle.LINE16,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PD2,
            SBE54tpsConfigurationDataParticle.LINE17,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PT1,
            SBE54tpsConfigurationDataParticle.LINE18,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PT2,
            SBE54tpsConfigurationDataParticle.LINE19,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PT3,
            SBE54tpsConfigurationDataParticle.LINE20,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PT4,
            SBE54tpsConfigurationDataParticle.LINE21,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PRESSURE_OFFSET,
            SBE54tpsConfigurationDataParticle.LINE22,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PRESSURE_RANGE,
            SBE54tpsConfigurationDataParticle.LINE23,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.BATTERY_TYPE,
            SBE54tpsConfigurationDataParticle.LINE24,
            lambda match : int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            direct_access=True)

        self._param_dict.add(Parameter.BAUD_RATE,
            SBE54tpsConfigurationDataParticle.LINE25,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.ENABLE_ALERTS,
            SBE54tpsConfigurationDataParticle.LINE26,
            lambda match : bool(int(match.group(1))),
            self._bool_to_int_string,
            startup_param=True,
            direct_access=True)

        self._param_dict.add(Parameter.UPLOAD_TYPE,
            SBE54tpsConfigurationDataParticle.LINE27,
            lambda match : int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            direct_access=True)

        self._param_dict.add(Parameter.SAMPLE_PERIOD,
            SBE54tpsConfigurationDataParticle.LINE28,
            lambda match : int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            direct_access=True)

        #
        # Event Counter
        #

        self._param_dict.add(Parameter.NUMBER_EVENTS,
            SBE54tpsEventCounterDataParticle.LINE1,
            lambda match : int(match.group(1)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.MAX_STACK,
            SBE54tpsEventCounterDataParticle.LINE1,
            lambda match : int(match.group(2)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.DEVICE_TYPE,
            SBE54tpsEventCounterDataParticle.LINE2,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.SERIAL_NUMBER,
            SBE54tpsEventCounterDataParticle.LINE2,
            lambda match : int(match.group(2)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.POWER_ON_RESET,
            SBE54tpsEventCounterDataParticle.LINE3,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.POWER_FAIL_RESET,
            SBE54tpsEventCounterDataParticle.LINE4,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.SERIAL_BYTE_ERROR,
            SBE54tpsEventCounterDataParticle.LINE5,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.COMMAND_BUFFER_OVERFLOW,
            SBE54tpsEventCounterDataParticle.LINE6,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.SERIAL_RECEIVE_OVERFLOW,
            SBE54tpsEventCounterDataParticle.LINE7,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.LOW_BATTERY,
            SBE54tpsEventCounterDataParticle.LINE8,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.SIGNAL_ERROR,
            SBE54tpsEventCounterDataParticle.LINE9,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.ERROR_10,
            SBE54tpsEventCounterDataParticle.LINE10,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.ERROR_12,
            SBE54tpsEventCounterDataParticle.LINE11,
            lambda match : int(match.group(1)),
            self._int_to_string)

        #
        # Hardware Data
        #

        self._param_dict.add(Parameter.DEVICE_TYPE,
            SBE54tpsHardwareDataParticle.LINE1,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.SERIAL_NUMBER,
            SBE54tpsHardwareDataParticle.LINE1,
            lambda match : int(match.group(2)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.MANUFACTURER,
            SBE54tpsHardwareDataParticle.LINE2,
            lambda match : string.upper(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.FIRMWARE_VERSION,
            SBE54tpsHardwareDataParticle.LINE3,
            lambda match : string.upper(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.FIRMWARE_DATE,
            SBE54tpsHardwareDataParticle.LINE4,
            lambda match : self._string_month_name_to_date(match.group(1)),
            self._date_to_string)

        self._param_dict.add(Parameter.HARDWARE_VERSION,
            SBE54tpsHardwareDataParticle.LINE5,
            lambda match : string.upper(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.PCB_SERIAL_NUMBER,
            SBE54tpsHardwareDataParticle.LINE6,
            lambda match : string.upper(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.PCB_TYPE,
            SBE54tpsHardwareDataParticle.LINE7,
            lambda match : string.upper(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.MANUFACTUR_DATE,
            SBE54tpsHardwareDataParticle.LINE8,
            lambda match : self._string_month_name_to_date(match.group(1)),
            self._date_to_string)

    def _got_chunk(self, chunk):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """


        result = self._extract_sample(SBE54tpsStatusDataParticle, STATUS_DATA_REGEX_MATCHER, chunk)

        result = self._extract_sample(SBE54tpsConfigurationDataParticle, CONFIGURATION_DATA_REGEX_MATCHER, chunk)

        result = self._extract_sample(SBE54tpsEventCounterDataParticle, EVENT_COUNTER_DATA_REGEX_MATCHER, chunk)

        result = self._extract_sample(SBE54tpsHardwareDataParticle, HARDWARE_DATA_REGEX_MATCHER, chunk)

        result = self._extract_sample(SBE54tpsSampleRefOscDataParticle, SAMPLE_REF_OSC_MATCHER, chunk)

        result = self._extract_sample(SBE54tpsSampleDataParticle, SAMPLE_DATA_REGEX_MATCHER, chunk)
        log.debug("%%% IN _got_chunk result = " + repr(result))

        """
        # @TODO need to enable this and wire the event, but not tonight.
        if result:
            # If this detects a sample, send a event change event whenever a SAMPLE_DATA_REGEX_MATCHER
            # this event handler will simply change mode to autosample if not already in autosample.
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

        """

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

        # Get old param dict config.
        old_config = self._param_dict.get_config()

        # Issue display commands and parse results.
        timeout = kwargs.get('timeout', TIMEOUT)



        response = self._do_cmd_resp(InstrumentCmds.GET_CONFIGURATION_DATA, timeout=timeout)
        for line in response.split(NEWLINE):
            self._param_dict.update(line)

        log.debug("GET_CONFIGURATION_DATA response = " + repr(response))

        response = self._do_cmd_resp(InstrumentCmds.GET_STATUS_DATA, timeout=timeout)
        for line in response.split(NEWLINE):
            self._param_dict.update(line)

        log.debug("GET_STATUS_DATA response = " + repr(response))

        response = self._do_cmd_resp(InstrumentCmds.GET_EVENT_COUNTER_DATA, timeout=timeout)
        for line in response.split(NEWLINE):
            self._param_dict.update(line)

        log.debug("GET_EVENT_COUNTER_DATA response = " + repr(response))

        response = self._do_cmd_resp(InstrumentCmds.GET_HARDWARE_DATA, timeout=timeout)
        for line in response.split(NEWLINE):
            self._param_dict.update(line)

        log.debug("GET_HARDWARE_DATA response = " + repr(response))


        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
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
    def _string_to_string(v):
        log.debug("IN _string_to_string")
        return v

    @staticmethod
    def _time_to_string(v):
        log.debug("IN _time_to_string")
        # return the passed in float of seconds since epoch to a string formatted time

        return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(v))

    @staticmethod
    def _date_to_string(v):
        log.debug("IN _date_to_string")
        # return the passed in float of seconds since epoch to a string formatted date
        # 2006-01-15
        return time.strftime("%Y-%m-%d", time.gmtime(v))

    @staticmethod
    def _string_month_number_to_date(v):
        log.debug("IN _string_to_date")
        # return a float of seconds since epoch for the passed in string formatted date
        # 2006-01-15
        py_timestamp = time.strptime(v, "%Y-%m-%d")
        return ntplib.system_to_ntp_time(time.mktime(py_timestamp))

    @staticmethod
    def _string_month_name_to_date(v):
        log.debug("IN _string_to_date")
        # return a float of seconds since epoch for the passed in string formatted date
        # 2006-01-15
        py_timestamp = time.strptime(v, "%b %d %Y")
        return ntplib.system_to_ntp_time(time.mktime(py_timestamp))

    @staticmethod
    def _string_to_datetime(v):
        # return a float of seconds since epoch for the passed in string formatted date_time
        # 2012-01-16T15:21:11

        py_timestamp = time.strptime(v, "%Y-%m-%dT%H:%M:%S")
        return ntplib.system_to_ntp_time(time.mktime(py_timestamp))


    @staticmethod
    def _bool_to_int_string(v):
        # return a string of an into of 1 or 0 to indicate true/false

        if True == v:
            return "1"
        elif False == v:
            return "0"
        else:
            return None
