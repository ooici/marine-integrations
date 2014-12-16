"""
@package mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver
@file marine-integrations/mi/instrument/seabird/sbe16plus_v2/ctdpf_jb/driver.py
@author Tapana Gupta
@brief Driver for the CTDPF-JB instrument
Release notes:

SBE Driver
"""

__author__ = 'Tapana Gupta'
__license__ = 'Apache 2.0'

import re
import time
import string

from mi.core.log import get_logger

log = get_logger()

from mi.core.common import BaseEnum
from mi.core.common import Units
from mi.core.util import dict_equal
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker

from mi.core.driver_scheduler import DriverSchedulerConfigKey, TriggerType

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException

from xml.dom.minidom import parseString

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType

from mi.instrument.seabird.sbe16plus_v2.driver import SBE16Protocol
from mi.instrument.seabird.sbe16plus_v2.driver import Prompt

from mi.instrument.seabird.driver import SeaBirdParticle
from mi.instrument.seabird.driver import SeaBirdInstrumentDriver
from mi.instrument.seabird.driver import NEWLINE
from mi.instrument.seabird.driver import TIMEOUT
from mi.instrument.seabird.driver import DEFAULT_ENCODER_KEY

# Driver constants
WAKEUP_TIMEOUT = 60
MIN_PUMP_DELAY = 0
MAX_PUMP_DELAY = 600
MIN_AVG_SAMPLES = 1
MAX_AVG_SAMPLES = 32767

DEFAULT_CLOCK_SYNC_INTERVAL = '00:00:00'
DEFAULT_STATUS_INTERVAL = '00:00:00'

SEND_OPTODE_COMMAND = "sendoptode="

###
# Driver Constant Definitions
###
class ParameterUnit(Units):
    TIME_INTERVAL = 'HH:MM:SS'


class ScheduledJob(BaseEnum):
    ACQUIRE_STATUS = 'acquire_status'
    CLOCK_SYNC = 'clock_sync'


class Command(BaseEnum):
    DS = 'ds'
    GET_CD = 'GetCD'
    GET_SD = 'GetSD'
    GET_CC = 'GetCC'
    GET_EC = 'GetEC'
    RESET_EC = 'ResetEC'
    GET_HD = 'GetHD'
    START_NOW = 'StartNow'
    STOP = 'Stop'
    TS = 'ts'
    SET = 'set'
    SEND_OPTODE = 'sendOptode'


class SendOptodeCommand(BaseEnum):
    GET_ANALOG_OUTPUT = 'get analog output'
    GET_CALPHASE = 'get calphase'
    GET_ENABLE_TEMP = 'get enable temperature'
    GET_ENABLE_TEXT = 'get enable text'
    GET_ENABLE_HUM_COMP = 'get enable humiditycomp'
    GET_ENABLE_AIR_SAT = 'get enable airsaturation'
    GET_ENABLE_RAW_DATA = 'get enable rawdata'
    GET_INTERVAL = 'get interval'
    GET_MODE = 'get mode'


class ProtocolState(BaseEnum):
    """
    Protocol states for SBE19. Cherry picked from DriverProtocolState
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS


class ProtocolEvent(BaseEnum):
    """
    Protocol events for SBE19. Cherry picked from DriverEvent enum.
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
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    SCHEDULED_CLOCK_SYNC = DriverEvent.SCHEDULED_CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    SCHEDULED_ACQUIRED_STATUS = 'PROTOCOL_EVENT_SCHEDULED_ACQUIRE_STATUS'


class Capability(BaseEnum):
    """
    Capabilities that are exposed to the user (subset of above)
    """
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS


class Parameter(DriverParameter):
    """
    Device specific parameters for SBE19.
    """
    DATE_TIME = "DateTime"
    PTYPE = "PType"
    VOLT0 = "Volt0"
    VOLT1 = "Volt1"
    VOLT2 = "Volt2"
    VOLT3 = "Volt3"
    VOLT4 = "Volt4"
    VOLT5 = "Volt5"
    SBE38 = "SBE38"
    WETLABS = "WetLabs"
    GTD = "GTD"
    DUAL_GTD = "DualGTD"
    SBE63 = "SBE63"
    OPTODE = "OPTODE"
    OUTPUT_FORMAT = "OutputFormat"
    NUM_AVG_SAMPLES = "Navg"
    MIN_COND_FREQ = "MinCondFreq"
    PUMP_DELAY = "PumpDelay"
    AUTO_RUN = "AutoRun"
    IGNORE_SWITCH = "IgnoreSwitch"
    LOGGING = "logging"
    CLOCK_INTERVAL = "ClockInterval"
    STATUS_INTERVAL = "StatusInterval"


class ConfirmedParameter(BaseEnum):
    """
    List of all parameters that require confirmation
    i.e. set sent twice to confirm.
    """
    PTYPE = Parameter.PTYPE
    SBE38 = Parameter.SBE38
    GTD = Parameter.GTD
    DUAL_GTD = Parameter.DUAL_GTD
    SBE63 = Parameter.SBE63
    OPTODE = Parameter.OPTODE
    WETLABS = Parameter.WETLABS
    VOLT0 = Parameter.VOLT0
    VOLT1 = Parameter.VOLT1
    VOLT2 = Parameter.VOLT2
    VOLT3 = Parameter.VOLT3
    VOLT4 = Parameter.VOLT4
    VOLT5 = Parameter.VOLT5


class DriverParameter(BaseEnum):
    """
    List of all driver specific parameters
    i.e. the instrument is not aware of these.
    """
    CLOCK_INTERVAL = Parameter.CLOCK_INTERVAL
    STATUS_INTERVAL = Parameter.STATUS_INTERVAL


###############################################################################
# Data Particles
###############################################################################

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    CTD_PARSED = 'ctdpf_optode_sample'
    DEVICE_STATUS = 'ctdpf_optode_status'
    DEVICE_CALIBRATION = 'ctdpf_optode_calibration_coefficients'
    DEVICE_HARDWARE = 'ctdpf_optode_hardware'
    DEVICE_CONFIGURATION = 'ctdpf_optode_configuration'
    OPTODE_SETTINGS = 'ctdpf_optode_settings'


class SBE19ConfigurationParticleKey(BaseEnum):
    SERIAL_NUMBER = "serial_number"

    SCANS_TO_AVERAGE = "scans_to_average"
    MIN_COND_FREQ = "min_cond_freq"
    PUMP_DELAY = "pump_delay"
    AUTO_RUN = "auto_run"
    IGNORE_SWITCH = "ignore_switch"

    BATTERY_TYPE = "battery_type"
    BATTERY_CUTOFF = "battery_cutoff"

    EXT_VOLT_0 = "ext_volt_0"
    EXT_VOLT_1 = "ext_volt_1"
    EXT_VOLT_2 = "ext_volt_2"
    EXT_VOLT_3 = "ext_volt_3"
    EXT_VOLT_4 = "ext_volt_4"
    EXT_VOLT_5 = "ext_volt_5"
    SBE38 = "sbe38"
    SBE63 = "sbe63"
    WETLABS = "wetlabs"
    OPTODE = "optode"
    GAS_TENSION_DEVICE = "gas_tension_device"

    ECHO_CHARACTERS = "echo_characters"
    OUTPUT_EXECUTED_TAG = "output_executed_tag"
    OUTPUT_FORMAT = "output_format"


# noinspection PyPep8Naming,PyListCreation
class SBE19ConfigurationParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_CONFIGURATION

    @staticmethod
    def regex():
        pattern = r'(<ConfigurationData.*?</ConfigurationData>)' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE19ConfigurationParticle.regex(), re.DOTALL)

    @staticmethod
    def resp_regex():
        pattern = r'(<ConfigurationData.*?</ConfigurationData>)'
        return pattern

    @staticmethod
    def resp_regex_compiled():
        return re.compile(SBE19ConfigurationParticle.resp_regex(), re.DOTALL)

    def _map_param_to_xml_tag(self, parameter_name):
        map_param_to_tag = {SBE19ConfigurationParticleKey.SCANS_TO_AVERAGE: "ScansToAverage",
                            SBE19ConfigurationParticleKey.MIN_COND_FREQ: "MinimumCondFreq",
                            SBE19ConfigurationParticleKey.PUMP_DELAY: "PumpDelay",
                            SBE19ConfigurationParticleKey.AUTO_RUN: "AutoRun",
                            SBE19ConfigurationParticleKey.IGNORE_SWITCH: "IgnoreSwitch",

                            SBE19ConfigurationParticleKey.BATTERY_TYPE: "Type",
                            SBE19ConfigurationParticleKey.BATTERY_CUTOFF: "CutOff",

                            SBE19ConfigurationParticleKey.EXT_VOLT_0: "ExtVolt0",
                            SBE19ConfigurationParticleKey.EXT_VOLT_1: "ExtVolt1",
                            SBE19ConfigurationParticleKey.EXT_VOLT_2: "ExtVolt2",
                            SBE19ConfigurationParticleKey.EXT_VOLT_3: "ExtVolt3",
                            SBE19ConfigurationParticleKey.EXT_VOLT_4: "ExtVolt4",
                            SBE19ConfigurationParticleKey.EXT_VOLT_5: "ExtVolt5",
                            SBE19ConfigurationParticleKey.SBE38: "SBE38",
                            SBE19ConfigurationParticleKey.SBE63: "SBE63",
                            SBE19ConfigurationParticleKey.WETLABS: "WETLABS",
                            SBE19ConfigurationParticleKey.OPTODE: "OPTODE",
                            SBE19ConfigurationParticleKey.GAS_TENSION_DEVICE: "GTD",

                            SBE19ConfigurationParticleKey.ECHO_CHARACTERS: "EchoCharacters",
                            SBE19ConfigurationParticleKey.OUTPUT_EXECUTED_TAG: "OutputExecutedTag",
                            SBE19ConfigurationParticleKey.OUTPUT_FORMAT: "OutputFormat",
        }
        return map_param_to_tag[parameter_name]

    def _build_parsed_values(self):
        """
        Parse the output of the getCD command
        @throws SampleException If there is a problem with sample creation
        """

        SERIAL_NUMBER = "SerialNumber"
        PROFILE_MODE = "ProfileMode"
        BATTERY = "Battery"
        DATA_CHANNELS = "DataChannels"

        # check to make sure there is a correct match before continuing
        match = SBE19ConfigurationParticle.regex_compiled().match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed configuration data: [%s]" %
                                  self.raw_data)

        dom = parseString(self.raw_data)
        root = dom.documentElement
        log.debug("root.tagName = %s", root.tagName)
        serial_number = int(root.getAttribute(SERIAL_NUMBER))
        result = [{DataParticleKey.VALUE_ID: SBE19ConfigurationParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number}]

        result.append(self._get_xml_parameter(root, SBE19ConfigurationParticleKey.ECHO_CHARACTERS, self.yesno2bool))
        result.append(self._get_xml_parameter(root, SBE19ConfigurationParticleKey.OUTPUT_EXECUTED_TAG, self.yesno2bool))
        result.append(self._get_xml_parameter(root, SBE19ConfigurationParticleKey.OUTPUT_FORMAT, str))

        element = self._extract_xml_elements(root, PROFILE_MODE)[0]
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.SCANS_TO_AVERAGE, int))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.MIN_COND_FREQ, int))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.PUMP_DELAY, int))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.AUTO_RUN, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.IGNORE_SWITCH, self.yesno2bool))

        element = self._extract_xml_elements(root, BATTERY)[0]
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.BATTERY_TYPE, str))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.BATTERY_CUTOFF))

        element = self._extract_xml_elements(root, DATA_CHANNELS)[0]
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.EXT_VOLT_0, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.EXT_VOLT_1, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.EXT_VOLT_2, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.EXT_VOLT_3, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.EXT_VOLT_4, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.EXT_VOLT_5, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.SBE38, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.WETLABS, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.OPTODE, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.SBE63, self.yesno2bool))
        result.append(
            self._get_xml_parameter(element, SBE19ConfigurationParticleKey.GAS_TENSION_DEVICE, self.yesno2bool))

        return result


class SBE19StatusParticleKey(BaseEnum):
    SERIAL_NUMBER = "serial_number"

    DATE_TIME = "date_time_string"
    LOGGING_STATE = "logging_status"
    NUMBER_OF_EVENTS = "num_events"

    BATTERY_VOLTAGE_MAIN = "battery_voltage_main"
    BATTERY_VOLTAGE_LITHIUM = "battery_voltage_lithium"
    OPERATIONAL_CURRENT = "operational_current"
    PUMP_CURRENT = "pump_current"
    EXT_V01_CURRENT = "ext_v01_current"
    SERIAL_CURRENT = "serial_current"

    MEMORY_FREE = "mem_free"
    NUMBER_OF_SAMPLES = "num_samples"
    SAMPLES_FREE = "samples_free"
    SAMPLE_LENGTH = "sample_length"
    PROFILES = "profiles"


# noinspection PyPep8Naming
class SBE19StatusParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_STATUS

    @staticmethod
    def regex():
        pattern = r'(<StatusData.*?</StatusData>)' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE19StatusParticle.regex(), re.DOTALL)

    @staticmethod
    def resp_regex():
        pattern = r'(<StatusData.*?</StatusData>)'
        return pattern

    @staticmethod
    def resp_regex_compiled():
        return re.compile(SBE19StatusParticle.resp_regex(), re.DOTALL)

    def _map_param_to_xml_tag(self, parameter_name):
        map_param_to_tag = {SBE19StatusParticleKey.BATTERY_VOLTAGE_MAIN: "vMain",
                            SBE19StatusParticleKey.BATTERY_VOLTAGE_LITHIUM: "vLith",
                            SBE19StatusParticleKey.OPERATIONAL_CURRENT: "iMain",
                            SBE19StatusParticleKey.PUMP_CURRENT: "iPump",
                            SBE19StatusParticleKey.EXT_V01_CURRENT: "iExt01",
                            SBE19StatusParticleKey.SERIAL_CURRENT: "iSerial",

                            SBE19StatusParticleKey.MEMORY_FREE: "Bytes",
                            SBE19StatusParticleKey.NUMBER_OF_SAMPLES: "Samples",
                            SBE19StatusParticleKey.SAMPLES_FREE: "SamplesFree",
                            SBE19StatusParticleKey.SAMPLE_LENGTH: "SampleLength",
                            SBE19StatusParticleKey.PROFILES: "Profiles",
        }
        return map_param_to_tag[parameter_name]

    def _build_parsed_values(self):
        """
        Parse the output of the getSD command
        @throws SampleException If there is a problem with sample creation
        """

        SERIAL_NUMBER = "SerialNumber"
        DATE_TIME = "DateTime"
        LOGGING_STATE = "LoggingState"
        EVENT_SUMMARY = "EventSummary"
        NUMBER_OF_EVENTS = "numEvents"
        POWER = "Power"
        MEMORY_SUMMARY = "MemorySummary"

        # check to make sure there is a correct match before continuing
        match = SBE19StatusParticle.regex_compiled().match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed status data: [%s]" %
                                  self.raw_data)

        dom = parseString(self.raw_data)
        root = dom.documentElement
        log.debug("root.tagName = %s", root.tagName)
        serial_number = int(root.getAttribute(SERIAL_NUMBER))
        date_time = self._extract_xml_element_value(root, DATE_TIME)
        logging_status = self._extract_xml_element_value(root, LOGGING_STATE)
        event_summary = self._extract_xml_elements(root, EVENT_SUMMARY)[0]
        number_of_events = int(event_summary.getAttribute(NUMBER_OF_EVENTS))
        result = [{DataParticleKey.VALUE_ID: SBE19StatusParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: SBE19StatusParticleKey.DATE_TIME,
                   DataParticleKey.VALUE: date_time},
                  {DataParticleKey.VALUE_ID: SBE19StatusParticleKey.LOGGING_STATE,
                   DataParticleKey.VALUE: logging_status},
                  {DataParticleKey.VALUE_ID: SBE19StatusParticleKey.NUMBER_OF_EVENTS,
                   DataParticleKey.VALUE: number_of_events},
        ]

        element = self._extract_xml_elements(root, POWER)[0]
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.BATTERY_VOLTAGE_MAIN))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.BATTERY_VOLTAGE_LITHIUM))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.OPERATIONAL_CURRENT))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.PUMP_CURRENT))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.EXT_V01_CURRENT))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.SERIAL_CURRENT))

        element = self._extract_xml_elements(root, MEMORY_SUMMARY)[0]
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.MEMORY_FREE, int))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.NUMBER_OF_SAMPLES, int))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.SAMPLES_FREE, int))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.SAMPLE_LENGTH, int))
        result.append(self._get_xml_parameter(element, SBE19StatusParticleKey.PROFILES, int))

        return result


class SBE19HardwareParticleKey(BaseEnum):
    SERIAL_NUMBER = "serial_number"
    FIRMWARE_VERSION = "firmware_version"
    FIRMWARE_DATE = "firmware_date"
    COMMAND_SET_VERSION = "command_set_version"
    PCB_SERIAL_NUMBER = "pcb_serial_number"
    ASSEMBLY_NUMBER = "assembly_number"
    MANUFACTURE_DATE = "manufacture_date"
    TEMPERATURE_SENSOR_SERIAL_NUMBER = 'temp_sensor_serial_number'
    CONDUCTIVITY_SENSOR_SERIAL_NUMBER = 'cond_sensor_serial_number'
    PRESSURE_SENSOR_TYPE = 'pressure_sensor_type'
    PRESSURE_SENSOR_SERIAL_NUMBER = 'strain_pressure_sensor_serial_number'
    VOLT0_TYPE = 'volt0_type'
    VOLT0_SERIAL_NUMBER = 'volt0_serial_number'
    VOLT1_TYPE = 'volt1_type'
    VOLT1_SERIAL_NUMBER = 'volt1_serial_number'


# noinspection PyPep8Naming
class SBE19HardwareParticle(SeaBirdParticle):
    _data_particle_type = DataParticleType.DEVICE_HARDWARE

    @staticmethod
    def regex():
        """
        Regular expression to match a getHD response pattern
        @return: regex string
        """
        pattern = r'(<HardwareData.*?</HardwareData>)' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(SBE19HardwareParticle.regex(), re.DOTALL)

    @staticmethod
    def resp_regex():
        """
        Regular expression to match a getHD response pattern
        @return: regex string
        """
        pattern = r'(<HardwareData.*?</HardwareData>)'
        return pattern

    @staticmethod
    def resp_regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(SBE19HardwareParticle.resp_regex(), re.DOTALL)

    def _build_parsed_values(self):
        """
        @throws SampleException If there is a problem with sample creation
        """

        SENSOR = "Sensor"
        TYPE = "type"
        ID = "id"
        PCB_SERIAL_NUMBER = "PCBSerialNum"
        ASSEMBLY_NUMBER = "AssemblyNum"
        SERIAL_NUMBER = "SerialNumber"
        FIRMWARE_VERSION = "FirmwareVersion"
        FIRMWARE_DATE = "FirmwareDate"
        COMMAND_SET_VERSION = "CommandSetVersion"
        PCB_ASSEMBLY = "PCBAssembly"
        MANUFACTURE_DATE = "MfgDate"
        INTERNAL_SENSORS = "InternalSensors"
        TEMPERATURE_SENSOR_ID = "Main Temperature"
        CONDUCTIVITY_SENSOR_ID = "Main Conductivity"
        PRESSURE_SENSOR_ID = "Main Pressure"
        EXTERNAL_SENSORS = "ExternalSensors"
        VOLT0 = "volt 0"
        VOLT1 = "volt 1"

        # check to make sure there is a correct match before continuing
        match = SBE19HardwareParticle.regex_compiled().match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed hardware data: [%s]" %
                                  self.raw_data)

        dom = parseString(self.raw_data)
        root = dom.documentElement
        log.debug("root.tagName = %s", root.tagName)
        serial_number = int(root.getAttribute(SERIAL_NUMBER))

        firmware_version = self._extract_xml_element_value(root, FIRMWARE_VERSION)
        firmware_date = self._extract_xml_element_value(root, FIRMWARE_DATE)
        command_set_version = self._extract_xml_element_value(root, COMMAND_SET_VERSION)
        manufacture_date = self._extract_xml_element_value(root, MANUFACTURE_DATE)

        pcb_assembly_elements = self._extract_xml_elements(root, PCB_ASSEMBLY)
        pcb_serial_number = []
        pcb_assembly = []
        for assembly in pcb_assembly_elements:
            pcb_serial_number.append(assembly.getAttribute(PCB_SERIAL_NUMBER))
            pcb_assembly.append(assembly.getAttribute(ASSEMBLY_NUMBER))

        temperature_sensor_serial_number = 0
        conductivity_sensor_serial_number = 0
        pressure_sensor_serial_number = 0
        pressure_sensor_type = ""
        volt0_serial_number = 0
        volt0_type = ""
        volt1_serial_number = 0
        volt1_type = ""

        internal_sensors_element = self._extract_xml_elements(root, INTERNAL_SENSORS)[0]
        sensors = self._extract_xml_elements(internal_sensors_element, SENSOR)

        for sensor in sensors:
            sensor_id = sensor.getAttribute(ID)
            if sensor_id == TEMPERATURE_SENSOR_ID:
                temperature_sensor_serial_number = int(self._extract_xml_element_value(sensor, SERIAL_NUMBER))
            elif sensor_id == CONDUCTIVITY_SENSOR_ID:
                conductivity_sensor_serial_number = int(self._extract_xml_element_value(sensor, SERIAL_NUMBER))
            elif sensor_id == PRESSURE_SENSOR_ID:
                pressure_sensor_serial_number = self._extract_xml_element_value(sensor, SERIAL_NUMBER)
                pressure_sensor_type = self._extract_xml_element_value(sensor, TYPE)

        external_sensors_element = self._extract_xml_elements(root, EXTERNAL_SENSORS)[0]
        sensors = self._extract_xml_elements(external_sensors_element, SENSOR)

        for sensor in sensors:
            sensor_id = sensor.getAttribute(ID)
            if sensor_id == VOLT0:
                volt0_serial_number = self._extract_xml_element_value(sensor, SERIAL_NUMBER)
                volt0_type = self._extract_xml_element_value(sensor, TYPE)
            elif sensor_id == VOLT1:
                volt1_serial_number = self._extract_xml_element_value(sensor, SERIAL_NUMBER)
                volt1_type = self._extract_xml_element_value(sensor, TYPE)

        result = [{DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.FIRMWARE_VERSION,
                   DataParticleKey.VALUE: firmware_version},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.FIRMWARE_DATE,
                   DataParticleKey.VALUE: firmware_date},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.COMMAND_SET_VERSION,
                   DataParticleKey.VALUE: command_set_version},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.MANUFACTURE_DATE,
                   DataParticleKey.VALUE: manufacture_date},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.PCB_SERIAL_NUMBER,
                   DataParticleKey.VALUE: pcb_serial_number},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.ASSEMBLY_NUMBER,
                   DataParticleKey.VALUE: pcb_assembly},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.TEMPERATURE_SENSOR_SERIAL_NUMBER,
                   DataParticleKey.VALUE: temperature_sensor_serial_number},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.CONDUCTIVITY_SENSOR_SERIAL_NUMBER,
                   DataParticleKey.VALUE: conductivity_sensor_serial_number},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.PRESSURE_SENSOR_SERIAL_NUMBER,
                   DataParticleKey.VALUE: pressure_sensor_serial_number},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.PRESSURE_SENSOR_TYPE,
                   DataParticleKey.VALUE: pressure_sensor_type},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.VOLT0_SERIAL_NUMBER,
                   DataParticleKey.VALUE: volt0_serial_number},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.VOLT0_TYPE,
                   DataParticleKey.VALUE: volt0_type},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.VOLT1_SERIAL_NUMBER,
                   DataParticleKey.VALUE: volt1_serial_number},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.VOLT1_TYPE,
                   DataParticleKey.VALUE: volt1_type},
        ]

        return result


class SBE19CalibrationParticleKey(BaseEnum):
    SERIAL_NUMBER = "serial_number"

    TEMP_SENSOR_SERIAL_NUMBER = "temp_sensor_serial_number"
    TEMP_CAL_DATE = "calibration_date_temperature"
    TA0 = "temp_coeff_ta0"
    TA1 = "temp_coeff_ta1"
    TA2 = "temp_coeff_ta2"
    TA3 = "temp_coeff_ta3"
    TOFFSET = "temp_coeff_offset"

    COND_SENSOR_SERIAL_NUMBER = "cond_sensor_serial_number"
    COND_CAL_DATE = "calibration_date_conductivity"
    CONDG = "cond_coeff_cg"
    CONDH = "cond_coeff_ch"
    CONDI = "cond_coeff_ci"
    CONDJ = "cond_coeff_cj"
    CPCOR = "cond_coeff_cpcor"
    CTCOR = "cond_coeff_ctcor"
    CSLOPE = "cond_coeff_cslope"

    PRES_SERIAL_NUMBER = "press_serial_number"
    PRES_CAL_DATE = "calibration_date_pressure"
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
    PRES_RANGE = "pressure_sensor_range"

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


# noinspection PyPep8Naming,PyPep8Naming
class SBE19CalibrationParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_CALIBRATION

    @staticmethod
    def regex():
        pattern = r'(<CalibrationCoefficients.*?</CalibrationCoefficients>)' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE19CalibrationParticle.regex(), re.DOTALL)

    @staticmethod
    def resp_regex():
        pattern = r'(<CalibrationCoefficients.*?</CalibrationCoefficients>)'
        return pattern

    @staticmethod
    def resp_regex_compiled():
        return re.compile(SBE19CalibrationParticle.resp_regex(), re.DOTALL)

    def _map_param_to_xml_tag(self, parameter_name):
        map_param_to_tag = {SBE19CalibrationParticleKey.TEMP_SENSOR_SERIAL_NUMBER: "SerialNum",
                            SBE19CalibrationParticleKey.TEMP_CAL_DATE: "CalDate",
                            SBE19CalibrationParticleKey.TA0: "TA0",
                            SBE19CalibrationParticleKey.TA1: "TA1",
                            SBE19CalibrationParticleKey.TA2: "TA2",
                            SBE19CalibrationParticleKey.TA3: "TA3",
                            SBE19CalibrationParticleKey.TOFFSET: "TOFFSET",

                            SBE19CalibrationParticleKey.COND_SENSOR_SERIAL_NUMBER: "SerialNum",
                            SBE19CalibrationParticleKey.COND_CAL_DATE: "CalDate",
                            SBE19CalibrationParticleKey.CONDG: "G",
                            SBE19CalibrationParticleKey.CONDH: "H",
                            SBE19CalibrationParticleKey.CONDI: "I",
                            SBE19CalibrationParticleKey.CONDJ: "J",
                            SBE19CalibrationParticleKey.CPCOR: "CPCOR",
                            SBE19CalibrationParticleKey.CTCOR: "CTCOR",
                            SBE19CalibrationParticleKey.CSLOPE: "CSLOPE",

                            SBE19CalibrationParticleKey.PRES_SERIAL_NUMBER: "SerialNum",
                            SBE19CalibrationParticleKey.PRES_CAL_DATE: "CalDate",
                            SBE19CalibrationParticleKey.PA0: "PA0",
                            SBE19CalibrationParticleKey.PA1: "PA1",
                            SBE19CalibrationParticleKey.PA2: "PA2",
                            SBE19CalibrationParticleKey.PTCA0: "PTCA0",
                            SBE19CalibrationParticleKey.PTCA1: "PTCA1",
                            SBE19CalibrationParticleKey.PTCA2: "PTCA2",
                            SBE19CalibrationParticleKey.PTCB0: "PTCB0",
                            SBE19CalibrationParticleKey.PTCB1: "PTCB1",
                            SBE19CalibrationParticleKey.PTCB2: "PTCB2",
                            SBE19CalibrationParticleKey.PTEMPA0: "PTEMPA0",
                            SBE19CalibrationParticleKey.PTEMPA1: "PTEMPA1",
                            SBE19CalibrationParticleKey.PTEMPA2: "PTEMPA2",
                            SBE19CalibrationParticleKey.POFFSET: "POFFSET",
                            SBE19CalibrationParticleKey.PRES_RANGE: "PRANGE",

                            SBE19CalibrationParticleKey.EXT_VOLT0_OFFSET: "OFFSET",
                            SBE19CalibrationParticleKey.EXT_VOLT0_SLOPE: "SLOPE",
                            SBE19CalibrationParticleKey.EXT_VOLT1_OFFSET: "OFFSET",
                            SBE19CalibrationParticleKey.EXT_VOLT1_SLOPE: "SLOPE",
                            SBE19CalibrationParticleKey.EXT_VOLT2_OFFSET: "OFFSET",
                            SBE19CalibrationParticleKey.EXT_VOLT2_SLOPE: "SLOPE",
                            SBE19CalibrationParticleKey.EXT_VOLT3_OFFSET: "OFFSET",
                            SBE19CalibrationParticleKey.EXT_VOLT3_SLOPE: "SLOPE",
                            SBE19CalibrationParticleKey.EXT_VOLT4_OFFSET: "OFFSET",
                            SBE19CalibrationParticleKey.EXT_VOLT4_SLOPE: "SLOPE",
                            SBE19CalibrationParticleKey.EXT_VOLT5_OFFSET: "OFFSET",
                            SBE19CalibrationParticleKey.EXT_VOLT5_SLOPE: "SLOPE",

                            SBE19CalibrationParticleKey.EXT_FREQ: "EXTFREQSF",
        }
        return map_param_to_tag[parameter_name]

    @staticmethod
    def _float_to_int(fl_str):
        return int(float(fl_str))

    def _build_parsed_values(self):
        """
        Parse the output of the getCC command
        @throws SampleException If there is a problem with sample creation
        """

        SERIAL_NUMBER = "SerialNumber"
        CALIBRATION = "Calibration"
        ID = "id"
        TEMPERATURE_SENSOR_ID = "Main Temperature"
        CONDUCTIVITY_SENSOR_ID = "Main Conductivity"
        PRESSURE_SENSOR_ID = "Main Pressure"
        VOLT0 = "Volt 0"
        VOLT1 = "Volt 1"
        VOLT2 = "Volt 2"
        VOLT3 = "Volt 3"
        VOLT4 = "Volt 4"
        VOLT5 = "Volt 5"
        EXTERNAL_FREQUENCY_CHANNEL = "external frequency channel"

        # check to make sure there is a correct match before continuing
        match = SBE19CalibrationParticle.regex_compiled().match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed calibration data: [%s]" %
                                  self.raw_data)

        dom = parseString(self.raw_data)
        root = dom.documentElement
        log.debug("root.tagName = %s", root.tagName)
        serial_number = int(root.getAttribute(SERIAL_NUMBER))
        result = [{DataParticleKey.VALUE_ID: SBE19CalibrationParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
        ]

        calibration_elements = self._extract_xml_elements(root, CALIBRATION)
        for calibration in calibration_elements:
            id_attr = calibration.getAttribute(ID)
            if id_attr == TEMPERATURE_SENSOR_ID:
                result.append(
                    self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TEMP_SENSOR_SERIAL_NUMBER, int))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TEMP_CAL_DATE, str))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TA0))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TA1))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TA2))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TA3))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TOFFSET))
            elif id_attr == CONDUCTIVITY_SENSOR_ID:
                result.append(
                    self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.COND_SENSOR_SERIAL_NUMBER, int))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.COND_CAL_DATE, str))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CONDG))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CONDH))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CONDI))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CONDJ))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CPCOR))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CTCOR))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CSLOPE))
            elif id_attr == PRESSURE_SENSOR_ID:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PRES_SERIAL_NUMBER, int))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PRES_CAL_DATE, str))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PA0))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PA1))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PA2))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PTCA0))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PTCA1))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PTCA2))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PTCB0))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PTCB1))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PTCB2))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PTEMPA0))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PTEMPA1))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PTEMPA2))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.POFFSET))
                result.append(
                    self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PRES_RANGE, self._float_to_int))
            elif id_attr == VOLT0:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT0_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT0_SLOPE))
            elif id_attr == VOLT1:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT1_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT1_SLOPE))
            elif id_attr == VOLT2:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT2_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT2_SLOPE))
            elif id_attr == VOLT3:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT3_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT3_SLOPE))
            elif id_attr == VOLT4:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT4_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT4_SLOPE))
            elif id_attr == VOLT5:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT5_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT5_SLOPE))
            elif id_attr == EXTERNAL_FREQUENCY_CHANNEL:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_FREQ))

        return result


class SBE19DataParticleKey(BaseEnum):
    TEMP = "temperature"
    CONDUCTIVITY = "conductivity"
    PRESSURE = "pressure"
    PRESSURE_TEMP = "pressure_temp"
    VOLT0 = "oxy_calphase"
    VOLT1 = "oxy_temp"
    OXYGEN = "oxygen"


class SBE19DataParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Sample:
       #04570F0A1E910828FC47BC59F199952C64C9

    Format:
       #ttttttccccccppppppvvvvvvvvvvvvoooooo

       Temperature = tttttt
       Conductivity = cccccc
       quartz pressure = pppppp
       quartz pressure temperature compensation = vvvv
       First external voltage = vvvv
       Second external voltage = vvvv
       Oxygen = oooooo
    """
    _data_particle_type = DataParticleType.CTD_PARSED

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        #ttttttccccccppppppvvvvvvvvvvvvoooooo
        pattern = r'#? *'  # patter may or may not start with a '
        pattern += r'([0-9A-F]{6})'  # temperature
        pattern += r'([0-9A-F]{6})'  # conductivity
        pattern += r'([0-9A-F]{6})'  # pressure
        pattern += r'([0-9A-F]{4})'  # pressure temp
        pattern += r'([0-9A-F]{4})'  # volt0
        pattern += r'([0-9A-F]{4})'  # volt1
        pattern += r'([0-9A-F]{6})'  # oxygen
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(SBE19DataParticle.regex())

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        the 7 measurements as stated above

        @throws SampleException If there is a problem with sample creation
        """
        match = SBE19DataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            temperature = self.hex2value(match.group(1))
            conductivity = self.hex2value(match.group(2))
            pressure = self.hex2value(match.group(3))
            pressure_temp = self.hex2value(match.group(4))
            volt0 = self.hex2value(match.group(5))
            volt1 = self.hex2value(match.group(6))
            oxygen = self.hex2value(match.group(7))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

        result = [{DataParticleKey.VALUE_ID: SBE19DataParticleKey.TEMP,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: SBE19DataParticleKey.CONDUCTIVITY,
                   DataParticleKey.VALUE: conductivity},
                  {DataParticleKey.VALUE_ID: SBE19DataParticleKey.PRESSURE,
                   DataParticleKey.VALUE: pressure},
                  {DataParticleKey.VALUE_ID: SBE19DataParticleKey.PRESSURE_TEMP,
                   DataParticleKey.VALUE: pressure_temp},
                  {DataParticleKey.VALUE_ID: SBE19DataParticleKey.VOLT0,
                   DataParticleKey.VALUE: volt0},
                  {DataParticleKey.VALUE_ID: SBE19DataParticleKey.VOLT1,
                   DataParticleKey.VALUE: volt1},
                  {DataParticleKey.VALUE_ID: SBE19DataParticleKey.OXYGEN,
                   DataParticleKey.VALUE: oxygen}]

        return result


class OptodeSettingsParticleKey(BaseEnum):
    CALPHASE = 'calphase'
    ENABLE_TEMP = 'enable_temperature'
    ENABLE_TEXT = 'enable_text'
    ENABLE_HUM_COMP = 'enable_humiditycomp'
    ENABLE_AIR_SAT = 'enable_airsaturation'
    ENABLE_RAW_DATA = 'enable_rawdata'
    ANALOG_OUTPUT = 'analog_output'
    INTERVAL = 'interval'
    MODE = 'mode'


class OptodeSettingsParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.OPTODE_SETTINGS

    @staticmethod
    def regex():
        # pattern for the first sendoptode command
        pattern = r'Optode RX = Analog Output'
        pattern += r'.*?'  # non-greedy match of all the junk between
        pattern += r'Optode RX = Mode[\s]*[\d]+[\s]+[\d]+[\s]+([\w\- \t]+)' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(OptodeSettingsParticle.regex(), re.DOTALL)

    def encoders(self):
        return {
            DEFAULT_ENCODER_KEY: str,

            OptodeSettingsParticleKey.CALPHASE: float,
            OptodeSettingsParticleKey.ENABLE_TEMP: self.yesno2bool,
            OptodeSettingsParticleKey.ENABLE_TEXT: self.yesno2bool,
            OptodeSettingsParticleKey.ENABLE_HUM_COMP: self.yesno2bool,
            OptodeSettingsParticleKey.ENABLE_AIR_SAT: self.yesno2bool,
            OptodeSettingsParticleKey.ENABLE_RAW_DATA: self.yesno2bool,
            OptodeSettingsParticleKey.INTERVAL: float,

        }


    # noinspection PyPep8
    def regex_multiline(self):
        return {
            OptodeSettingsParticleKey.ANALOG_OUTPUT: r'Optode RX = Analog Output[\s]*[\d]+[\s]+[\d]+[\s]+([\w]+)',
            OptodeSettingsParticleKey.CALPHASE: r'Optode RX = CalPhase\[Deg][\s]+[\d]+[\s]+[\d]+[\s]+(\d+.\d+)',
            OptodeSettingsParticleKey.ENABLE_TEMP: r'Optode RX = Enable Temperature[\s]+[\d]+[\s]+[\d]+[\s]+(Yes|No)',
            OptodeSettingsParticleKey.ENABLE_TEXT: r'Optode RX = Enable Text[\s]*[\d]+[\s]+[\d]+[\s]+(Yes|No)',
            OptodeSettingsParticleKey.ENABLE_HUM_COMP: r'Optode RX = Enable HumidityComp[\s]*[\d]+[\s]+[\d]+[\s]+(Yes|No)',
            OptodeSettingsParticleKey.ENABLE_AIR_SAT: r'Optode RX = Enable AirSaturation[\s]*[\d]+[\s]+[\d]+[\s]+(Yes|No)',
            OptodeSettingsParticleKey.ENABLE_RAW_DATA: r'Optode RX = Enable Rawdata[\s]*[\d]+[\s]+[\d]+[\s]+(Yes|No)',
            OptodeSettingsParticleKey.INTERVAL: r'Optode RX = Interval[\s]+[\d]+[\s]+[\d]+[\s]+(\d+.\d+)',
            OptodeSettingsParticleKey.MODE: r'Optode RX = Mode[\s]*[\d]+[\s]+[\d]+[\s]+([\w\- \t]+)',

        }

    def _build_parsed_values(self):
        """
        Parse the output of the SendOptode commands

        @throws SampleException If there is a problem with sample creation
        """
        match = OptodeSettingsParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed optode data: [%s]" %
                                  self.raw_data)

        try:
            return self._get_multiline_values()
        except ValueError as e:
            raise SampleException("ValueError while decoding optode output: [%s]" % e)


###############################################################################
# Driver
###############################################################################

class InstrumentDriver(SeaBirdInstrumentDriver):
    """
    InstrumentDriver subclass
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
        self._protocol = SBE19Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

# noinspection PyPep8Naming
class SBE19Protocol(SBE16Protocol):
    """
    Instrument protocol class for SBE19 Driver
    Subclasses SBE16Protocol
    """

    def __init__(self, prompts, newline, driver_event):
        """
        SBE19Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The SBE19 newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build SBE19 protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE,
                                       self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_CONFIGURATION,
                                       self._handler_command_get_configuration)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE,
                                       self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT,
                                       self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC,
                                       self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SCHEDULED_CLOCK_SYNC,
                                       self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS,
                                       self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SCHEDULED_ACQUIRED_STATUS,
                                       self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE,
                                       self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_STATUS,
                                       self._handler_autosample_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SCHEDULED_ACQUIRED_STATUS,
                                       self._handler_autosample_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET_CONFIGURATION,
                                       self._handler_autosample_get_configuration)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SCHEDULED_CLOCK_SYNC,
                                       self._handler_autosample_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER,
                                       self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT,
                                       self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT,
                                       self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT,
                                       self._handler_direct_access_stop_direct)


        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_driver_dict()
        self._build_command_dict()
        self._build_param_dict()

        # Add build handlers for device commands.

        self._add_build_handler(Command.DS, self._build_simple_command)
        self._add_build_handler(Command.GET_CD, self._build_simple_command)
        self._add_build_handler(Command.GET_SD, self._build_simple_command)
        self._add_build_handler(Command.GET_CC, self._build_simple_command)
        self._add_build_handler(Command.GET_EC, self._build_simple_command)
        self._add_build_handler(Command.RESET_EC, self._build_simple_command)
        self._add_build_handler(Command.GET_HD, self._build_simple_command)

        self._add_build_handler(Command.START_NOW, self._build_simple_command)
        self._add_build_handler(Command.STOP, self._build_simple_command)
        self._add_build_handler(Command.TS, self._build_simple_command)
        self._add_build_handler(Command.SET, self._build_set_command)
        self._add_build_handler(Command.SEND_OPTODE, self._build_send_optode_command)

        # Add response handlers for device commands.
        # these are here to ensure that correct responses to the commands are received before the next command is sent
        self._add_response_handler(Command.DS, self._parse_dsdc_response)
        self._add_response_handler(Command.SET, self._parse_set_response)
        self._add_response_handler(Command.GET_SD, self._validate_GetSD_response)
        self._add_response_handler(Command.GET_HD, self._validate_GetHD_response)
        self._add_response_handler(Command.GET_CD, self._validate_GetCD_response)
        self._add_response_handler(Command.GET_CC, self._validate_GetCC_response)
        self._add_response_handler(Command.GET_EC, self._validate_GetEC_response)
        self._add_response_handler(Command.SEND_OPTODE, self._validate_SendOptode_response)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        self._chunker = StringChunker(self.sieve_function)

        #Setup schedulable commands
        self._setup_scheduler_config()

    def _setup_scheduler_config(self):
        """
        Set up auto scheduler configuration.
        """
        clock_interval_seconds = self._param_dict.format(Parameter.CLOCK_INTERVAL)
        status_interval_seconds = self._param_dict.format(Parameter.STATUS_INTERVAL)

        log.debug("clock sync interval: %s" % clock_interval_seconds)
        log.debug("status interval: %s" % status_interval_seconds)

        if DriverConfigKey.SCHEDULER in self._startup_config:

            self._startup_config[DriverConfigKey.SCHEDULER][ScheduledJob.CLOCK_SYNC] = {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                    DriverSchedulerConfigKey.SECONDS: clock_interval_seconds}
            }

            self._startup_config[DriverConfigKey.SCHEDULER][ScheduledJob.ACQUIRE_STATUS] = {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                    DriverSchedulerConfigKey.SECONDS: status_interval_seconds}
            }

        else:

            self._startup_config[DriverConfigKey.SCHEDULER] = {
                ScheduledJob.CLOCK_SYNC: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.SECONDS: clock_interval_seconds
                    }
                }, ScheduledJob.ACQUIRE_STATUS: {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                    DriverSchedulerConfigKey.SECONDS: status_interval_seconds
                }
            },
            }

        # Start the scheduler if it is not running
        if not self._scheduler:
            self.initialize_scheduler()

        #First remove the scheduler, if it exists
        if not self._scheduler_callback.get(ScheduledJob.CLOCK_SYNC) is None:
            self._remove_scheduler(ScheduledJob.CLOCK_SYNC)
            log.debug("Removed scheduler for clock sync")

        if not self._scheduler_callback.get(ScheduledJob.ACQUIRE_STATUS) is None:
            self._remove_scheduler(ScheduledJob.ACQUIRE_STATUS)
            log.debug("Removed scheduler for acquire status")

        #Now Add the scheduler
        if clock_interval_seconds > 0:
            self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        if status_interval_seconds > 0:
            self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS, ProtocolEvent.SCHEDULED_ACQUIRED_STATUS)


    @staticmethod
    def sieve_function(raw_data):
        """ The method that splits samples
        Over-ride sieve function to handle additional particles.
        """
        matchers = []
        return_list = []

        matchers.append(SBE19DataParticle.regex_compiled())
        matchers.append(SBE19HardwareParticle.regex_compiled())
        matchers.append(SBE19CalibrationParticle.regex_compiled())
        matchers.append(SBE19StatusParticle.regex_compiled())
        matchers.append(SBE19ConfigurationParticle.regex_compiled())
        matchers.append(OptodeSettingsParticle.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _filter_capabilities(self, events):
        """
        """
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        self._verify_not_readonly(*args, **kwargs)

        scheduling_interval_changed = False
        old_config = self._param_dict.get_config()

        #check values that the instrument doesn't validate
        #handle special cases for driver specific parameters
        for key, val in params.iteritems():
            if key == Parameter.PUMP_DELAY and (val < MIN_PUMP_DELAY or val > MAX_PUMP_DELAY):
                raise InstrumentParameterException("pump delay out of range")
            elif key == Parameter.NUM_AVG_SAMPLES and (val < MIN_AVG_SAMPLES or val > MAX_AVG_SAMPLES):
                raise InstrumentParameterException("num average samples out of range")

            # set driver specific parameters
            elif key == Parameter.CLOCK_INTERVAL or key == Parameter.STATUS_INTERVAL:
                old_val = self._param_dict.get(key)
                if val != old_val:
                    self._param_dict.set_value(key, val)
                    scheduling_interval_changed = True

        for key, val in params.iteritems():
            log.debug("KEY = %s VALUE = %s", key, val)

            if key in ConfirmedParameter.list():
                # We add a write delay here because this command has to be sent
                # twice, the write delay allows it to process the first command
                # before it receives the beginning of the second.
                self._do_cmd_resp(Command.SET, key, val, write_delay=0.2)
            elif key not in DriverParameter.list():
                self._do_cmd_resp(Command.SET, key, val, **kwargs)

        if scheduling_interval_changed:
            self._handle_scheduling_params_changed(old_config)

        log.debug("set complete, update params")
        self._update_params()

    def _handle_scheduling_params_changed(self, old_config):
        """
        Required actions when scheduling parameters change
        """
        self._setup_scheduler_config()

        new_config = self._param_dict.get_config()

        if not dict_equal(new_config, old_config):
            log.debug("Updated params, sending config change event")
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, next_agent_state), (ProtocolState.COMMAND or
        SBE16State.AUTOSAMPLE, next_agent_state) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the device response does not correspond to
        an expected state.
        """

        log.debug("_handler_unknown_discover")

        logging = self._is_logging(*args, **kwargs)
        log.debug("are we logging? %s", logging)

        if logging is None:
            raise InstrumentProtocolException('_handler_unknown_discover - unable to to determine state')
        elif logging:
            next_state = ProtocolState.AUTOSAMPLE
            next_agent_state = ResourceAgentState.STREAMING
        else:
            # We want to sync the clock upon initialization
            self._wakeup(timeout=WAKEUP_TIMEOUT)
            self._sync_clock(Command.SET, Parameter.DATE_TIME, TIMEOUT, time_format="%Y-%m-%dT%H:%M:%S")

            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.IDLE

        log.debug("_handler_unknown_discover. result start: %s", next_state)
        return next_state, next_agent_state


    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        self._init_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)


    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        (next_agent_state, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        result = None

        self._start_logging(*args, **kwargs)

        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return next_state, (next_agent_state, result)

    def _handler_command_get_configuration(self, *args, **kwargs):
        """
        Run the GetCC command.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        next_agent_state = None

        kwargs['timeout'] = TIMEOUT
        result = self._do_cmd_resp(Command.GET_CC, *args, **kwargs)
        log.debug("_handler_command_get_configuration: GetCC Response: %s", result)

        return next_state, (next_agent_state, result)

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None

        result = []

        result.append(self._do_cmd_resp(Command.GET_SD, response_regex=SBE19StatusParticle.regex_compiled(),
                                   timeout=TIMEOUT))
        log.debug("_handler_command_acquire_status: GetSD Response: %s", result)
        result.append(self._do_cmd_resp(Command.GET_HD, response_regex=SBE19HardwareParticle.regex_compiled(),
                                    timeout=TIMEOUT))
        log.debug("_handler_command_acquire_status: GetHD Response: %s", result)
        result.append(self._do_cmd_resp(Command.GET_CD, response_regex=SBE19ConfigurationParticle.regex_compiled(),
                                    timeout=TIMEOUT))
        log.debug("_handler_command_acquire_status: GetCD Response: %s", result)
        result.append(self._do_cmd_resp(Command.GET_CC, response_regex=SBE19CalibrationParticle.regex_compiled(),
                                    timeout=TIMEOUT))
        log.debug("_handler_command_acquire_status: GetCC Response: %s", result)
        result.append(self._do_cmd_resp(Command.GET_EC, timeout=TIMEOUT))
        log.debug("_handler_command_acquire_status: GetEC Response: %s", result)

        #Reset the event counter right after getEC
        self._do_cmd_resp(Command.RESET_EC, timeout=TIMEOUT)

        #Now send commands to the Optode to get its status
        #Stop the optode first, need to send the command twice
        stop_command = "stop"
        start_command = "start"
        self._do_cmd_resp(Command.SEND_OPTODE, stop_command, timeout=TIMEOUT)
        time.sleep(2)
        self._do_cmd_resp(Command.SEND_OPTODE, stop_command, timeout=TIMEOUT)
        time.sleep(3)

        #Send all the 'sendoptode=' commands one by one
        optode_commands = SendOptodeCommand.list()
        for command in optode_commands:
            log.debug("Sending optode command: %s" % command)
            result.append(self._do_cmd_resp(Command.SEND_OPTODE, command, timeout=TIMEOUT))
            log.debug("_handler_command_acquire_status: SendOptode Response: %s", result)

        #restart the optode
        self._do_cmd_resp(Command.SEND_OPTODE, start_command, timeout=TIMEOUT)

        return next_state, (next_agent_state, ''.join(result))


    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        #stop logging before initializing parameters
        #can't set parameters in autosample mode
        self._stop_logging(*args, **kwargs)

        self._init_params()

        #start logging again
        self._start_logging(*args, **kwargs)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None

        result = []

        # When in autosample this command requires two wakeups to get to the right prompt
        self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)
        self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)

        result.append(self._do_cmd_resp(Command.GET_SD, response_regex=SBE19StatusParticle.regex_compiled(),
                                   timeout=TIMEOUT))
        log.debug("_handler_autosample_acquire_status: GetSD Response: %s", result)
        result.append(self._do_cmd_resp(Command.GET_HD, response_regex=SBE19HardwareParticle.regex_compiled(),
                                    timeout=TIMEOUT))
        log.debug("_handler_autosample_acquire_status: GetHD Response: %s", result)
        result.append(self._do_cmd_resp(Command.GET_CD, response_regex=SBE19ConfigurationParticle.regex_compiled(),
                                    timeout=TIMEOUT))
        log.debug("_handler_autosample_acquire_status: GetCD Response: %s", result)
        result.append(self._do_cmd_resp(Command.GET_CC, response_regex=SBE19CalibrationParticle.regex_compiled(),
                                    timeout=TIMEOUT))
        log.debug("_handler_autosample_acquire_status: GetCC Response: %s", result)
        result.append(self._do_cmd_resp(Command.GET_EC, timeout=TIMEOUT))
        log.debug("_handler_autosample_acquire_status: GetEC Response: %s", result)

        #Reset the event counter right after getEC
        self._do_cmd_no_resp(Command.RESET_EC)

        return next_state, (next_agent_state, ''.join(result))

    def _handler_autosample_get_configuration(self, *args, **kwargs):
        """
        GetCC from SBE16.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        next_agent_state = None

        # When in autosample this command requires two wakeups to get to the right prompt
        self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)
        self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)

        kwargs['timeout'] = TIMEOUT
        result = self._do_cmd_resp(Command.GET_CC, *args, **kwargs)
        log.debug("_handler_autosample_get_configuration: GetCC Response: %s", result)

        return next_state, (next_agent_state, result)

    # need to override this method as time format for SBE19 is different
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

        self._wakeup(timeout=WAKEUP_TIMEOUT)

        log.debug("Performing Clock Sync...")
        self._sync_clock(Command.SET, Parameter.DATE_TIME, TIMEOUT, time_format="%Y-%m-%dT%H:%M:%S")

        return next_state, (next_agent_state, result)

    # need to override this method as time format for SBE19 is different
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

        log.debug("Performing Clock Sync in autosample mode...")
        self._autosample_clock_sync(*args, **kwargs)

        return next_state, (next_agent_state, result)


    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """

        #discover the state to go to next
        next_state, next_agent_state = self._handler_unknown_discover()

        return next_state, (next_agent_state, None)


    #need to override this method as our Command set is different
    def _start_logging(self, *args, **kwargs):
        """
        Command the instrument to start logging
        @param timeout: how long to wait for a prompt
        @return: True if successful
        @raise: InstrumentProtocolException if failed to start logging
        """
        log.debug("Start Logging!")
        if self._is_logging():
            return True

        self._do_cmd_no_resp(Command.START_NOW, *args, **kwargs)
        time.sleep(2)

        if not self._is_logging(20):
            raise InstrumentProtocolException("failed to start logging")

        return True


    # must override this method as our Command set is different
    def _stop_logging(self, *args, **kwargs):
        """
        Command the instrument to stop logging
        @param timeout: how long to wait for a prompt
        @return: True if successful
        @raise: InstrumentTimeoutException if prompt isn't seen
        @raise: InstrumentProtocolException failed to stop logging
        """
        log.debug("Stop Logging!")

        self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)
        self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)

        # Issue the stop command.
        # We can get here from handle_unknown_discover, hence it's possible that the current state is unknown
        # handle_unknown_discover checks if we are currently streaming before we get here.
        if self.get_current_state() in [ProtocolState.AUTOSAMPLE, ProtocolState.UNKNOWN]:
            log.debug("sending stop logging command")
            kwargs['timeout'] = TIMEOUT
            self._do_cmd_resp(Command.STOP, *args, **kwargs)
        else:
            log.debug("Instrument not logging, current state %s", self.get_current_state())

        if self._is_logging(*args, **kwargs):
            raise InstrumentProtocolException("failed to stop logging")

        return True

    def _is_logging(self, *args, **kwargs):
        """
        Wake up the instrument and inspect the prompt to determine if we
        are in streaming
        @param: timeout - Command timeout
        @return: True - instrument logging, False - not logging,
                 None - unknown logging state
        @raise: InstrumentProtocolException if we can't identify the prompt
        """
        self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)

        self._update_params()

        pd = self._param_dict.get_all()
        return pd.get(Parameter.LOGGING)


    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Wake the device then issue
        display status and display calibration commands. The parameter
        dict will match line output and udpate itself.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)

        # For some reason when in streaming we require a second wakeup
        self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)

        # Get old param dict config.
        old_config = self._param_dict.get_config()

        # Issue display commands and parse results.
        log.debug("device status from _update_params")
        self._do_cmd_resp(Command.DS, timeout=TIMEOUT)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()

        log.debug("Old Config: %s", old_config)
        log.debug("New Config: %s", new_config)
        if not dict_equal(new_config, old_config) and self._protocol_fsm.get_current_state() != ProtocolState.UNKNOWN:
            log.debug("parameters updated, sending event")
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        else:
            log.debug("no configuration change.")


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

            set_cmd = '%s=%s%s' % (param, str_val, NEWLINE)

            # Some set commands need to be sent twice to confirm
            if param in ConfirmedParameter.list():
                set_cmd = set_cmd + set_cmd

        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return set_cmd


    def _build_send_optode_command(self, cmd, command):
        """
        Build handler for sendoptode command.
        @param cmd The command to build.
        @param command The optode command.
        @ retval The set command to be sent to the device.

        """
        return "%s=%s%s" % (cmd, command, self._newline)


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


    ########################################################################
    # response handlers.
    ########################################################################
    def _validate_GetSD_response(self, response, prompt):
        """
        validation handler for GetSD command
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("_validate_GetSD_response: GetSD command encountered error; type='%s' msg='%s'", error[0],
                      error[1])
            raise InstrumentProtocolException('GetSD command failure: type="%s" msg="%s"' % (error[0], error[1]))

        if not SBE19StatusParticle.resp_regex_compiled().search(response):
            log.error('_validate_GetSD_response: GetSD command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetSD command not recognized: %s.' % response)

        return response

    def _validate_GetHD_response(self, response, prompt):
        """
        validation handler for GetHD command
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("GetHD command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentProtocolException('GetHD command failure: type="%s" msg="%s"' % (error[0], error[1]))

        if not SBE19HardwareParticle.resp_regex_compiled().search(response):
            log.error('_validate_GetHD_response: GetHD command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetHD command not recognized: %s.' % response)

        return response

    def _validate_GetCD_response(self, response, prompt):
        """
        validation handler for GetCD command
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("GetCD command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentProtocolException('GetCD command failure: type="%s" msg="%s"' % (error[0], error[1]))

        if not SBE19ConfigurationParticle.resp_regex_compiled().search(response):
            log.error('_validate_GetCD_response: GetCD command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetCD command not recognized: %s.' % response)

        return response

    def _validate_GetCC_response(self, response, prompt):
        """
        validation handler for GetCC command
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("GetCC command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentProtocolException('GetCC command failure: type="%s" msg="%s"' % (error[0], error[1]))

        if not SBE19CalibrationParticle.resp_regex_compiled().search(response):
            log.error('_validate_GetCC_response: GetCC command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetCC command not recognized: %s.' % response)

        return response

    def _validate_GetEC_response(self, response, prompt):
        """
        validation handler for GetEC command
        @param response command response string.
        @throws InstrumentProtocolException if command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("GetEC command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentProtocolException('GetEC command failure: type="%s" msg="%s"' % (error[0], error[1]))

        return response

    def _validate_SendOptode_response(self, response, prompt):
        """
        validation handler for GetEC command
        @param response command response string.
        @throws InstrumentProtocolException if command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("SendOptode command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentProtocolException('Send Optode command failure: type="%s" msg="%s"' % (error[0], error[1]))

        return response

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.ACQUIRE_SAMPLE, display_name="Acquire Sample")
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="Start Autosample")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="Stop Autosample")
        self._cmd_dict.add(Capability.CLOCK_SYNC, display_name="Clock Sync")
        self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name="Acquire Status")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with SBE19 parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.

        self._param_dict.add(Parameter.DATE_TIME,
                             r'SBE 19plus V ([\w.]+) +SERIAL NO. (\d+) +(\d{2} [a-zA-Z]{3,4} \d{4} +[\d:]+)',
                             lambda match: string.upper(match.group(3)),
                             self._date_time_string_to_numeric,
                             type=ParameterDictType.STRING,
                             display_name="Date/Time",
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.LOGGING,
                             r'status = (not )?logging',
                             lambda match: False if (match.group(1)) else True,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Is Logging",
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PTYPE,
                             r'pressure sensor = ([\w\s]+),',
                             self._pressure_sensor_to_int,
                             str,
                             type=ParameterDictType.INT,
                             display_name="Pressure Sensor Type",
                             startup_param=True,
                             direct_access=True,
                             default_value=1,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.VOLT0,
                             r'Ext Volt 0 = ([\w]+)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 0",
                             startup_param=True,
                             direct_access=True,
                             default_value=True,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.VOLT1,
                             r'Ext Volt 1 = ([\w]+)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 1",
                             startup_param=True,
                             direct_access=True,
                             default_value=True,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.VOLT2,
                             r'Ext Volt 2 = ([\w]+)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 2",
                             startup_param=True,
                             direct_access=True,
                             default_value=False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.VOLT3,
                             r'Ext Volt 3 = ([\w]+)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 3",
                             startup_param=True,
                             direct_access=True,
                             default_value=False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.VOLT4,
                             r'Ext Volt 4 = ([\w]+)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 4",
                             startup_param=True,
                             direct_access=True,
                             default_value=False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.VOLT5,
                             r'Ext Volt 5 = ([\w]+)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 5",
                             startup_param=True,
                             direct_access=True,
                             default_value=False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.SBE38,
                             r'SBE 38 = (yes|no)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="SBE38 Attached",
                             startup_param=True,
                             direct_access=True,
                             default_value=False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.WETLABS,
                             r'WETLABS = (yes|no)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Enable Wetlabs Sensor",
                             startup_param=True,
                             direct_access=True,
                             default_value=False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.GTD,
                             r'Gas Tension Device = (yes|no)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="GTD Attached",
                             startup_param=True,
                             direct_access=True,
                             default_value=False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.DUAL_GTD,
                             r'Gas Tension Device = (yes|no)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Dual GTD Attached",
                             startup_param=True,
                             direct_access=True,
                             default_value=False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.SBE63,
                             r'SBE63 = (yes|no)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="SBE63 Attached",
                             startup_param=True,
                             direct_access=True,
                             default_value=False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.OPTODE,
                             r'OPTODE = (yes|no)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Optode Attached",
                             startup_param=True,
                             direct_access=True,
                             default_value=True,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.OUTPUT_FORMAT,
                             r'output format = (raw HEX)',
                             self._output_format_string_2_int,
                             int,
                             type=ParameterDictType.INT,
                             display_name="Output Format",
                             startup_param=True,
                             direct_access=True,
                             default_value=0,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.NUM_AVG_SAMPLES,
                             r'number of scans to average = ([\d]+)',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.INT,
                             display_name="Scans To Average",
                             startup_param=True,
                             default_value=4,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.MIN_COND_FREQ,
                             r'minimum cond freq = ([\d]+)',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.INT,
                             display_name="Minimum Conductivity Frequency",
                             startup_param=True,
                             default_value=500,
                             units=ParameterUnit.HERTZ,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.PUMP_DELAY,
                             r'pump delay = ([\d]+) sec',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.INT,
                             display_name="Pump Delay",
                             startup_param=True,
                             default_value=60,
                             units=ParameterUnit.SECOND,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.AUTO_RUN,
                             r'autorun = (yes|no)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Auto Run",
                             startup_param=True,
                             direct_access=True,
                             default_value=False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.IGNORE_SWITCH,
                             r'ignore magnetic switch = (yes|no)',
                             lambda match: True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Ignore Switch",
                             startup_param=True,
                             direct_access=True,
                             default_value=True,
                             visibility=ParameterDictVisibility.IMMUTABLE)

        #Scheduling parameters (driver specific)
        # Instrument is not aware of these
        self._param_dict.add(Parameter.CLOCK_INTERVAL,
                             'bogus',
                             str,
                             self._get_seconds_from_time_string,
                             type=ParameterDictType.STRING,
                             display_name="Clock Interval",
                             startup_param=True,
                             default_value=DEFAULT_CLOCK_SYNC_INTERVAL,
                             units=ParameterUnit.TIME_INTERVAL,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.STATUS_INTERVAL,
                             'bogus',
                             str,
                             self._get_seconds_from_time_string,
                             type=ParameterDictType.STRING,
                             display_name="Status Interval",
                             startup_param=True,
                             default_value=DEFAULT_STATUS_INTERVAL,
                             units=ParameterUnit.TIME_INTERVAL,
                             visibility=ParameterDictVisibility.READ_WRITE)


    def _got_chunk(self, chunk, timestamp):
        """
        Over-ride sieve function to handle additional particles.
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        for particle_class in SBE19HardwareParticle, SBE19DataParticle, SBE19CalibrationParticle, \
                              SBE19ConfigurationParticle, SBE19StatusParticle, OptodeSettingsParticle:
            if self._extract_sample(particle_class, particle_class.regex_compiled(), chunk, timestamp):
                return

        raise InstrumentProtocolException("Unhandled chunk %s" % chunk)


    def _autosample_clock_sync(self, *args, **kwargs):
        """
        Sync the clock in autosample mode. Stop logging before sync, restart logging after.
        """
        error = None

        try:
            # Switch to command mode
            self._stop_logging(*args, **kwargs)

            # Sync the clock
            self._sync_clock(Command.SET, Parameter.DATE_TIME, TIMEOUT, time_format="%Y-%m-%dT%H:%M:%S")

        # Catch all errors so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging(*args, **kwargs)

        if error:
            raise error


    ########################################################################
    # Static helpers
    ########################################################################

    @staticmethod
    def _date_time_string_to_numeric(date_time_string):
        """
        convert string from "2014-03-27T14:36:15" to numeric "mmddyyyyhhmmss"
        """
        return time.strftime("%m%d%Y%H%M%S", time.strptime(date_time_string, "%Y-%m-%dT%H:%M:%S"))

    @staticmethod
    def _get_seconds_from_time_string(time_string):
        """
        extract the number of seconds from the specified time interval in "hh:mm:ss"
        """

        # Set the interval to 0 by default
        if time_string is None:
            return  0

        # Calculate the interval in seconds from the time string
        interval = time.strptime(time_string, "%H:%M:%S")
        return interval.tm_hour * 3600 + interval.tm_min * 60 + interval.tm_sec

    @staticmethod
    def _output_format_string_2_int(format_string):
        """
        Convert an output format from an string to an int
        @param format_string sbe output format as string or regex match
        @retval int representation of output format
        @raise InstrumentParameterException if format unknown
        """
        if not isinstance(format_string, str):
            format_string = format_string.group(1)

        if format_string.lower() == "raw hex":
            return 0
        elif format_string.lower() == "converted hex":
            return 1
        elif format_string.lower() == "raw decimal":
            return 2
        elif format_string.lower() == "converted decimal":
            return 3
        elif format_string.lower() == "converted hex for afm":
            return 4
        elif format_string.lower() == "converted xml uvic":
            return 5
        else:
            raise InstrumentParameterException("output format unknown: %s" % format_string)
