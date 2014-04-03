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

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.data_particle import DataParticleKey, CommonDataParticleType
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException

from xml.dom.minidom import parseString

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType

from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolState
from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolEvent
from mi.instrument.seabird.sbe16plus_v2.driver import Capability
from mi.instrument.seabird.sbe16plus_v2.driver import SBE16Protocol
from mi.instrument.seabird.sbe16plus_v2.driver import Prompt

from mi.instrument.seabird.driver import SeaBirdParticle
from mi.instrument.seabird.driver import SeaBirdInstrumentDriver
from mi.instrument.seabird.driver import NEWLINE
from mi.instrument.seabird.driver import TIMEOUT

WAKEUP_TIMEOUT = 60

class ScheduledJob(BaseEnum):
    ACQUIRE_STATUS = 'acquire_status'
    CONFIGURATION_DATA = "configuration_data"
    CLOCK_SYNC = 'clock_sync'


class Command(BaseEnum):

        GET_CD = 'GetCD'
        GET_SD = 'GetSD'
        GET_CC = 'GetCC'
        GET_EC = 'GetEC'
        RESET_EC = 'ResetEC'
        GET_HD = 'GetHD'
        START_NOW = 'StartNow'
        STOP = 'Stop'
        TS = 'ts'

        #TODO: not specified in IOS
        SET = 'set'


class Parameter(DriverParameter):
    """
    Device specific parameters for SBE19.
    """
    DATE_TIME = "DateTime"

    #TODO: do we need this?
    LOGGING = "logging"

    ECHO = "Echo"
    OUTPUT_EXEC_TAG = 'OutputExecutedTag'
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
    DUAL_GTD = "DUAL_GTD"
    TGTD = "TGTD"
    SEND_GTD = "SendGTD"
    OPTODE = "OPTODE"
    SEND_OPTODE = "SendOptode"
    OUTPUT_FORMAT = "OutputFormat"
    PROFILING_MODE = "MP"
    NUM_AVG_SAMPLES = "Navg"
    MIN_COND_FREQ = "MinCondFreq"
    PUMP_DELAY = "PumpDelay"
    AUTO_RUN = "AutoRun"
    IGNORE_SWITCH = "IgnoreSwitch"


###############################################################################
# Data Particles
###############################################################################

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    CTD_PARSED = 'ctdpf_sample'
    DEVICE_STATUS = 'ctdpf_status'
    DEVICE_CALIBRATION = 'ctdpf_calibration_coefficients'
    DEVICE_HARDWARE = 'ctdpf_hardware'
    DEVICE_CONFIGURATION = 'ctdpf_configuration'


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
    WETLABS = "wetlabs"
    OPTODE = "optode"
    GAS_TENSION_DEVICE = "gas_tension_device"

    ECHO_CHARACTERS = "echo_characters"
    OUTPUT_EXECUTED_TAG = "output_executed_tag"
    OUTPUT_FORMAT = "output_format"


class SBE19ConfigurationParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_CONFIGURATION

    @staticmethod
    def regex():
        pattern = r'<ConfigurationData.*?</ConfigurationData>' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE19ConfigurationParticle.regex(), re.DOTALL)

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
        log.debug("root.tagName = %s" %root.tagName)
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
        result.append(self._get_xml_parameter(element, SBE19ConfigurationParticleKey.GAS_TENSION_DEVICE, self.yesno2bool))

        return result



class SBE19StatusParticleKey(BaseEnum):
    SERIAL_NUMBER = "serial_number"

    DATE_TIME = "date_time_string"
    LOGGING_STATE = "logging_state"
    NUMBER_OF_EVENTS = "num_events"

    BATTERY_VOLTAGE_MAIN = "battery_voltage_main"
    BATTERY_VOLTAGE_LITHIUM = "battery_voltage_lithium"
    OPERATIONAL_CURRENT = "operational_current"
    PUMP_CURRENT = "pump_current"
    EXT_V01_CURRENT = "ext_v01_current"
    SERIAL_CURRENT = "serial_current"

    MEMORY_FREE = "mem_free"
    NUMBER_OF_SAMPLES = "numm_samples"
    SAMPLES_FREE = "samples_free"
    SAMPLE_LENGTH = "sample_length"
    PROFILES = "profiles"


class SBE19StatusParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_STATUS

    @staticmethod
    def regex():
        pattern = r'<StatusData.*?</StatusData>' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE19StatusParticle.regex(), re.DOTALL)

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
        log.debug("root.tagName = %s" %root.tagName)
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
    MANUFACTURER = "manufacturer"
    FIRMWARE_VERSION = "firmware_version"
    FIRMWARE_DATE = "firmware_date"
    COMMAND_SET_VERSION = "command_set_version"
    PCB_SERIAL_NUMBER = "pcb_serial_number"
    ASSEMBLY_NUMBER = "assembly_number"
    MANUFACTURE_DATE = "manufacture_date"
    TEMPERATURE_SENSOR_TYPE = 'temperature_sensor_type'
    TEMPERATURE_SENSOR_SERIAL_NUMBER = 'temperature_sensor_serial_number'
    CONDUCTIVITY_SENSOR_TYPE = 'temperature_sensor_type'
    CONDUCTIVITY_SENSOR_SERIAL_NUMBER = 'conductivity_sensor_serial_number'
    PRESSURE_SENSOR_TYPE = 'pressure_sensor_type'
    QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER = 'quartz_pressure_sensor_serial_number'

class SBE19HardwareParticle(SeaBirdParticle):

    _data_particle_type = DataParticleType.DEVICE_HARDWARE

    @staticmethod
    def regex():
        """
        Regular expression to match a getHD response pattern
        @return: regex string
        """
        pattern = r'<HardwareData.*?</HardwareData>' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(SBE19HardwareParticle.regex(), re.DOTALL)

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
        MANUFACTURER = "Manufacturer"
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
        VOLT2 = "volt 2"
        VOLT3 = "volt 3"
        VOLT4 = "volt 4"
        VOLT5 = "volt 5"
        SERIAL = "serial"

        # check to make sure there is a correct match before continuing
        match = SBE19HardwareParticle.regex_compiled().match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed hardware data: [%s]" %
                                  self.raw_data)

        dom = parseString(self.raw_data)
        root = dom.documentElement
        log.debug("root.tagName = %s" %root.tagName)
        serial_number = int(root.getAttribute(SERIAL_NUMBER))

        manufacturer = self._extract_xml_element_value(root, MANUFACTURER)
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

        internal_sensors_element = self._extract_xml_elements(root, INTERNAL_SENSORS)[0]
        sensors = self._extract_xml_elements(internal_sensors_element, SENSOR)

        temperature_sensor_serial_number = 0
        temperature_sensor_type = ""
        conductivity_sensor_serial_number = 0
        conductivity_sensor_type = ""
        pressure_sensor_serial_number = 0
        pressure_sensor_type = ""

        for sensor in sensors:
            sensor_id = sensor.getAttribute(ID)
            if sensor_id == TEMPERATURE_SENSOR_ID:
                temperature_sensor_serial_number = int(self._extract_xml_element_value(sensor, SERIAL_NUMBER))
                temperature_sensor_type = self._extract_xml_element_value(sensor, TYPE)
            elif sensor_id == CONDUCTIVITY_SENSOR_ID:
                conductivity_sensor_serial_number = int(self._extract_xml_element_value(sensor, SERIAL_NUMBER))
                conductivity_sensor_type = self._extract_xml_element_value(sensor, TYPE)
            elif sensor_id == PRESSURE_SENSOR_ID:
                pressure_sensor_serial_number = int(self._extract_xml_element_value(sensor, SERIAL_NUMBER))
                pressure_sensor_type = self._extract_xml_element_value(sensor, TYPE)

        #TODO: do we care about external sensors?
        #external_sensors_element = self._extract_xml_elements(root, EXTERNAL_SENSORS)[0]
        #sensors = self._extract_xml_elements(external_sensors_element, SENSOR)
        #for sensor in sensors:
        #    sensor_id = sensor.getAttribute(ID)
        #    if sensor_id == VOLT0:
        #        volt0_serial_number = self._extract_xml_element_value(sensor, SERIAL_NUMBER)
        #        volt0_sensor_type = self._extract_xml_element_value(sensor, TYPE)


        result = [{DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.MANUFACTURER,
                   DataParticleKey.VALUE: manufacturer},
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
                   {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.TEMPERATURE_SENSOR_TYPE,
                   DataParticleKey.VALUE: temperature_sensor_type},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.CONDUCTIVITY_SENSOR_SERIAL_NUMBER,
                   DataParticleKey.VALUE: conductivity_sensor_serial_number},
                   {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.CONDUCTIVITY_SENSOR_TYPE,
                   DataParticleKey.VALUE: conductivity_sensor_type},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER,
                   DataParticleKey.VALUE: pressure_sensor_serial_number},
                  {DataParticleKey.VALUE_ID: SBE19HardwareParticleKey.PRESSURE_SENSOR_TYPE,
                   DataParticleKey.VALUE: pressure_sensor_type},
                  ]

        return result


class SBE19CalibrationParticleKey(BaseEnum):
    SERIAL_NUMBER = "serial_number"

    TEMP_SENSOR_SERIAL_NUMBER = " temp_sensor_serial_number "
    TEMP_CAL_DATE = "calibration_date_temperature"
    TA0 = "temp_coeff_ta0"
    TA1 = "temp_coeff_ta1"
    TA2 = "temp_coeff_ta2"
    TA3 = "temp_coeff_ta3"
    TOFFSET = "temp_coeff_offset"

    COND_SENSOR_SERIAL_NUMBER = " cond_sensor_serial_number "
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
    PTEMPA0 = "press_coeff_tempa0"
    PTEMPA1 = "press_coeff_tempa1"
    PTEMPA2 = "press_coeff_tempa2"
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


class SBE19CalibrationParticle(SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_CALIBRATION

    @staticmethod
    def regex():
        pattern = r'<CalibrationCoefficients.*?</CalibrationCoefficients>' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE19CalibrationParticle.regex(), re.DOTALL)

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

    def _float_to_int(self, str):
        return int(float(str))

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
        log.debug("root.tagName = %s" %root.tagName)
        serial_number = int(root.getAttribute(SERIAL_NUMBER))
        result = [{DataParticleKey.VALUE_ID: SBE19CalibrationParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                 ]

        calibration_elements = self._extract_xml_elements(root, CALIBRATION)
        for calibration in calibration_elements:
            id = calibration.getAttribute(ID)
            if id == TEMPERATURE_SENSOR_ID:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TEMP_SENSOR_SERIAL_NUMBER, str))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TEMP_CAL_DATE, str))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TA0))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TA1))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TA2))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TA3))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.TOFFSET))
            elif id == CONDUCTIVITY_SENSOR_ID:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.COND_SENSOR_SERIAL_NUMBER, str))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.COND_CAL_DATE, str))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CONDG))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CONDH))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CONDI))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CONDJ))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CPCOR))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CTCOR))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.CSLOPE))
            elif id == PRESSURE_SENSOR_ID:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PRES_SERIAL_NUMBER, str))
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
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.PRES_RANGE, self._float_to_int))
            elif id == VOLT0:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT0_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT0_SLOPE))
            elif id == VOLT1:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT1_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT1_SLOPE))
            elif id == VOLT2:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT2_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT2_SLOPE))
            elif id == VOLT3:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT3_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT3_SLOPE))
            elif id == VOLT4:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT4_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT4_SLOPE))
            elif id == VOLT5:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT5_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_VOLT5_SLOPE))
            elif id == EXTERNAL_FREQUENCY_CHANNEL:
                result.append(self._get_xml_parameter(calibration, SBE19CalibrationParticleKey.EXT_FREQ))

        return result


class SBE19DataParticleKey(BaseEnum):
    TEMP = "temperature"
    CONDUCTIVITY = "conductivity"
    PRESSURE = "pressure"
    PRESSURE_TEMP = "pressure_temp"
    VOLT0 = "volt0"
    VOLT1 = "volt1"
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
        pattern = r'#? *' # patter may or may not start with a '
        pattern += r'([0-9A-F]{6})' # temperature
        pattern += r'([0-9A-F]{6})' # conductivity
        pattern += r'([0-9A-F]{6})' # pressure
        pattern += r'([0-9A-F]{4})' # pressure temp
        pattern += r'([0-9A-F]{4})' # volt0
        pattern += r'([0-9A-F]{4})' # volt1
        pattern += r'([0-9A-F]{6})' # oxygen
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
        C, T, and D values (with appropriate tags)

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

###############################################################################
# Driver
###############################################################################

class SBE19InstrumentDriver(SeaBirdInstrumentDriver):
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
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_CONFIGURATION, self._handler_command_get_configuration)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.RESET_EC, self._handler_command_reset_ec)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.TEST, self._handler_command_test)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS, self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.QUIT_SESSION, self._handler_command_autosample_quit_session)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_STATUS, self._handler_autosample_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET_CONFIGURATION, self._handler_autosample_get_configuration)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_autosample_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.ENTER, self._handler_test_enter)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.EXIT, self._handler_test_exit)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.RUN_TEST, self._handler_test_run_tests)
        self._protocol_fsm.add_handler(ProtocolState.TEST, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)


        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_driver_dict()
        self._build_command_dict()
        self._build_param_dict()

        # Add build handlers for device commands.

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


        #TODO: Maybe we would like to implement DS and DCal, and use the response handlers in the base class to update
        # the param dict. In that case, build_param_dict would need to be updated to not parse XML.

        # Add response handlers for device commands.
        # these are here to ensure that correct responses to the commands are received before the next command is sent
        self._add_response_handler(Command.SET, self._parse_set_response)
        self._add_response_handler(Command.GET_SD, self._validate_GetSD_response)
        self._add_response_handler(Command.GET_HD, self._validate_GetHD_response)
        self._add_response_handler(Command.GET_CD, self._validate_GetCD_response)
        self._add_response_handler(Command.GET_CC, self._validate_GetCC_response)
        self._add_response_handler(Command.GET_EC, self._validate_GetEC_response)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        self._chunker = StringChunker(self.sieve_function)

        #TODO: what other commands are schedulable?
        self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS, ProtocolEvent.ACQUIRE_STATUS)
        self._add_scheduler_event(ScheduledJob.CONFIGURATION_DATA, ProtocolEvent.GET_CONFIGURATION)
        self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.SCHEDULED_CLOCK_SYNC)


    #TODO: Investigate the following methods inherited from base class:
    # _filter_capabilities
    # _set_params
    # _update_params

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

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _handler_command_get_configuration(self, *args, **kwargs):
        """
        GetCC from SBE16.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = TIMEOUT
        result = self._do_cmd_resp(Command.GET_CC, expected_prompt=Prompt.EXECUTED, *args, **kwargs)
        log.debug("_handler_command_get_configuration: GetCC Response: %s", result)

        return (next_state, (next_agent_state, result))

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None

        result = self._do_cmd_resp(Command.GET_SD, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_command_acquire_status: GetSD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_HD, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_command_acquire_status: GetHD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_CD, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_command_acquire_status: GetCD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_CC, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_command_acquire_status: GetCC Response: %s", result)

        return (next_state, (next_agent_state, result))

    def _handler_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None

        # When in autosample this command requires two wakeups to get to the right prompt
        prompt = self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)
        prompt = self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)

        result = self._do_cmd_resp(Command.GET_SD, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_autosample_acquire_status: GetSD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_HD, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_autosample_acquire_status: GetHD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_CD, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_autosample_acquire_status: GetCD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_CC, timeout=TIMEOUT, expected_prompt=Prompt.EXECUTED)
        log.debug("_handler_autosample_acquire_status: GetCC Response: %s", result)

        log.debug("_handler_autosample_acquire_status: sending the QS command to restart sampling")
        self._protocol_fsm.on_event(ProtocolEvent.QUIT_SESSION)

        return (next_state, (next_agent_state, result))


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
        result = None

        # When in autosample this command requires two wakeups to get to the right prompt
        prompt = self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)
        prompt = self._wakeup(timeout=WAKEUP_TIMEOUT, delay=0.3)

        kwargs['timeout'] = TIMEOUT
        result = self._do_cmd_resp(Command.GET_CC, expected_prompt=Prompt.EXECUTED, *args, **kwargs)
        log.debug("_handler_autosample_get_configuration: GetCC Response: %s", result)

        log.debug("_handler_autosample_get_configuration: sending the QS command to restart sampling")
        self._protocol_fsm.on_event(ProtocolEvent.QUIT_SESSION)

        return (next_state, (next_agent_state, result))


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
            log.error("_validate_GetSD_response: GetSD command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentProtocolException('GetSD command failure: type="%s" msg="%s"' % (error[0], error[1]))

        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            log.error('_validate_GetSD_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetSD command - correct instrument prompt missing: %s.' % response)

        if not SBE19StatusParticle.regex_compiled().search(response):
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

        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            log.error('_validate_GetHD_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetHD command - correct instrument prompt missing: %s.' % response)

        if not SBE19HardwareParticle.regex_compiled().search(response):
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

        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            log.error('_validate_GetCD_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetCD command - correct instrument prompt missing: %s.' % response)

        if not SBE19ConfigurationParticle.regex_compiled().search(response):
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

        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            log.error('_validate_GetCC_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetCC command - correct instrument prompt missing: %s.' % response)

        if not SBE19CalibrationParticle.regex_compiled().search(response):
            log.error('_validate_GetCC_response: GetCC command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetCC command not recognized: %s.' % response)

        return response

    def _validate_GetEC_response(self, response, prompt):
        """
        validation handler for GetEC command
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if command misunderstood.
        """
        error = self._find_error(response)

        if error:
            log.error("GetEC command encountered error; type='%s' msg='%s'", error[0], error[1])
            raise InstrumentProtocolException('GetEC command failure: type="%s" msg="%s"' % (error[0], error[1]))

        if prompt not in [Prompt.COMMAND, Prompt.EXECUTED]:
            log.error('_validate_GetEC_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetEC command - correct instrument prompt missing: %s.' % response)

        if not SBE19CalibrationParticle.regex_compiled().search(response):
            log.error('_validate_GetEC_response: GetEC command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetEC command not recognized: %s.' % response)

        return response

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with SBE19 parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.

        #TODO: re-visit visibility for all parameters once IOS is in good shape

        #TODO: verify if this lambda function is correct, check for completeness of DATE_TIME
        self._param_dict.add(Parameter.DATE_TIME,
                             r'(\d{4})-(\d{2})-(\d{2})T(\d{2})\:(\d{2})\:(\d{2})',
                             lambda match : match,
                             self._string_to_numeric_date_time_string,
                             type=ParameterDictType.STRING,
                             display_name="Date/Time",
                             #expiration=0,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.ECHO,
                             r'<EchoCharacters>(yes|no)</EchoCharacters>',
                             lambda match : True if match.group(1)=='yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Echo Characters",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.LOGGING,
                             r'<LoggingState>(not )?logging</LoggingState>',
                             lambda match : False if (match.group(1)) else True,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Is Logging",
                             #expiration=0,
                             visibility=ParameterDictVisibility.READ_ONLY)

        #TODO: RegEx for this one?
        self._param_dict.add(Parameter.OUTPUT_EXEC_TAG,
                             r'.',
                             lambda match : True,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Output Execute Tag",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)

        #TODO: RegEx for this one? This should always be 1
        self._param_dict.add(Parameter.PTYPE,
                             r'',
                             1,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Pressure Sensor Type",
                             startup_param = True,
                             direct_access = True,
                             default_value = 1,
                             visibility=ParameterDictVisibility.READ_WRITE)

        #TODO: default value is conditional for Volt0 and Volt1
        #Current defaults assume Anderra Optode
        self._param_dict.add(Parameter.VOLT0,
                             r'<ExtVolt0>([\w]+)</ExtVolt0>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 0",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.VOLT1,
                             r'<ExtVolt1>([\w]+)</ExtVolt1>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 1",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.VOLT2,
                             r'<ExtVolt2>([\w]+)</ExtVolt2>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 2",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.VOLT3,
                             r'<ExtVolt3>([\w]+)</ExtVolt3>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 3",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.VOLT4,
                             r'<ExtVolt4>([\w]+)</ExtVolt4>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 4",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.VOLT5,
                             r'<ExtVolt5>([\w]+)</ExtVolt5>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 5",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.SBE38,
                             r'<SBE38>(yes|no)</SBE38>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="SBE38 Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.WETLABS,
                             r'<WETLABS>(yes|no)</WETLABS>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Enable Wetlabs sensor",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.GTD,
                             r'<GTD>(yes|no)</GTD>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="GTD Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.DUAL_GTD,
                             r'<DualGTD>(yes|no)</DualGTD>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Dual GTD Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.TGTD,
                             r'<TGTD>(yes|no)</TGTD>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="GTD Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.READ_WRITE)

        #TODO: This assumes we have Anderra Optode
        self._param_dict.add(Parameter.OPTODE,
                             r'<OPTODE>(yes|no)</OPTODE>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Optode Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.READ_WRITE)


        self._param_dict.add(Parameter.OUTPUT_FORMAT,
                             r'<OutputFormat>([\w]+)</OutputFormat>',
                             self._output_format_string_2_int,
                             int,
                             type=ParameterDictType.INT,
                             display_name="Output Format",
                             startup_param = True,
                             direct_access = True,
                             default_value = 0,
                             visibility=ParameterDictVisibility.READ_WRITE)

        self._param_dict.add(Parameter.NUM_AVG_SAMPLES,
                             r'<ScansToAverage>([\d]+)</ScansToAverage>',
                             lambda match : match.group(1),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Scans To Average",
                             startup_param = True,
                             direct_access = True,
                             default_value = 4,
                             visibility=ParameterDictVisibility.READ_WRITE)

        self._param_dict.add(Parameter.MIN_COND_FREQ,
                             r'<MinimumCondFreq>([\d]+)</MinimumCondFreq>',
                             lambda match : match.group(1),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Minimum Conductivity Frequency",
                             startup_param = True,
                             direct_access = True,
                             default_value = 500,
                             visibility=ParameterDictVisibility.IMMUTABLE)

        self._param_dict.add(Parameter.PUMP_DELAY,
                             r'<PumpDelay>([\d]+)</PumpDelay>',
                             lambda match : match.group(1),
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Pump Delay",
                             startup_param = True,
                             direct_access = True,
                             default_value = 60,
                             visibility=ParameterDictVisibility.READ_WRITE)

        self._param_dict.add(Parameter.AUTO_RUN,
                             r'<AutoRun>(yes|no)</AutoRun>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Auto Run",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)

        self._param_dict.add(Parameter.IGNORE_SWITCH,
                             r'<IgnoreSwitch>(yes|no)</IgnoreSwitch>',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Ignore Switch",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.IMMUTABLE)


        #TODO: SendGTD, SendOptode, MP?



    def _got_chunk(self, chunk, timestamp):
        """
        Over-ride sieve function to handle additional particles.
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        if not (self._extract_sample(SBE19HardwareParticle, SBE19HardwareParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE19DataParticle, SBE19DataParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE19CalibrationParticle, SBE19CalibrationParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE19ConfigurationParticle, SBE19ConfigurationParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE19StatusParticle, SBE19StatusParticle.regex_compiled(), chunk, timestamp)):
            raise InstrumentProtocolException("Unhandled chunk %s" %chunk)


    ########################################################################
    # Static helpers
    ########################################################################

    @staticmethod
    def _string_to_numeric_date_time_string(date_time_string):
        """
        convert string from "2014-03-27T14:36:15" to numeric "mmddyyyyhhmmss"
        """
        return time.strftime("%m%d%Y%H%M%S", time.strptime(date_time_string, "%Y-%m-%dT%H:%M:%S"))


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
        elif(format_string.lower() == "converted hex for afm"):
            return 4
        elif(format_string.lower() == "converted xml uvic"):
            return 5
        else:
            raise InstrumentParameterException("output format unknown: %s" % format_string)
