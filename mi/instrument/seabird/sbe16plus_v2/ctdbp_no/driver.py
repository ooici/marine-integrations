"""
@package mi.instrument.seabird.sbe16plus_v2.ctdbp_no.driver
@file mi/instrument/seabird/sbe16plus_v2/ctdbp_no/driver.py
@author Tapana Gupta
@brief Driver class for sbe16plus V2 CTD instrument.
"""

__author__ = 'Tapana Gupta'
__license__ = 'Apache 2.0'


import re
import time
import string

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.util import dict_equal
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.instrument_fsm import InstrumentFSM
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

from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import Command
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import SendOptodeCommand
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import SBE19Protocol
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import DataParticleType
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import SBE19DataParticle
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import SBE19HardwareParticle
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import SBE19StatusParticle
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import OptodeSettingsParticle

from mi.instrument.seabird.sbe16plus_v2.driver import Prompt

from mi.instrument.seabird.driver import SeaBirdParticle
from mi.instrument.seabird.driver import SeaBirdInstrumentDriver

from mi.instrument.seabird.driver import NEWLINE
from mi.instrument.seabird.driver import TIMEOUT
from mi.instrument.seabird.driver import DEFAULT_ENCODER_KEY

import mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver

WAKEUP_TIMEOUT = 60

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

class ConfirmedParameter(BaseEnum):
    """
    List of all parameters that require confirmation
    i.e. set sent twice to confirm.
    """
    PTYPE    =  Parameter.PTYPE
    SBE38    =  Parameter.SBE38
    GTD      =  Parameter.GTD
    DUAL_GTD =  Parameter.DUAL_GTD
    SBE63    =  Parameter.SBE63
    OPTODE   =  Parameter.OPTODE
    WETLABS  =  Parameter.WETLABS
    VOLT0    =  Parameter.VOLT0
    VOLT1    =  Parameter.VOLT1
    VOLT2    =  Parameter.VOLT2
    VOLT3    =  Parameter.VOLT3
    VOLT4    =  Parameter.VOLT4
    VOLT5    =  Parameter.VOLT5


###############################################################################
# Particles
###############################################################################


class SBE16NOHardwareParticleKey(BaseEnum):
    SERIAL_NUMBER = "serial_number"
    MANUFACTURER = "manufacturer"
    FIRMWARE_VERSION = "firmware_version"
    FIRMWARE_DATE = "firmware_date"
    COMMAND_SET_VERSION = "command_set_version"
    PCB_SERIAL_NUMBER = "pcb_serial_number"
    ASSEMBLY_NUMBER = "assembly_number"
    MANUFACTURE_DATE = "manufacture_date"
    TEMPERATURE_SENSOR_TYPE = 'temperature_sensor_type'
    TEMPERATURE_SENSOR_SERIAL_NUMBER = 'temp_sensor_serial_number'
    CONDUCTIVITY_SENSOR_TYPE = 'conductivity_sensor_type'
    CONDUCTIVITY_SENSOR_SERIAL_NUMBER = 'cond_sensor_serial_number'
    PRESSURE_SENSOR_TYPE = 'pressure_sensor_type'
    PRESSURE_SENSOR_SERIAL_NUMBER = 'quartz_pressure_sensor_serial_number'
    VOLT0_TYPE = 'volt0_type'
    VOLT0_SERIAL_NUMBER = 'volt0_serial_number'
    VOLT1_TYPE = 'volt1_type'
    VOLT1_SERIAL_NUMBER = 'volt1_serial_number'


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

        temperature_sensor_serial_number = 0
        temperature_sensor_type = ""
        conductivity_sensor_serial_number = 0
        conductivity_sensor_type = ""
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
                temperature_sensor_type = self._extract_xml_element_value(sensor, TYPE)
            elif sensor_id == CONDUCTIVITY_SENSOR_ID:
                conductivity_sensor_serial_number = int(self._extract_xml_element_value(sensor, SERIAL_NUMBER))
                conductivity_sensor_type = self._extract_xml_element_value(sensor, TYPE)
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

        result = [{DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.MANUFACTURER,
                   DataParticleKey.VALUE: manufacturer},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.FIRMWARE_VERSION,
                   DataParticleKey.VALUE: firmware_version},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.FIRMWARE_DATE,
                   DataParticleKey.VALUE: firmware_date},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.COMMAND_SET_VERSION,
                   DataParticleKey.VALUE: command_set_version},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.MANUFACTURE_DATE,
                   DataParticleKey.VALUE: manufacture_date},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.PCB_SERIAL_NUMBER,
                   DataParticleKey.VALUE: pcb_serial_number},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.ASSEMBLY_NUMBER,
                   DataParticleKey.VALUE: pcb_assembly},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.TEMPERATURE_SENSOR_SERIAL_NUMBER,
                   DataParticleKey.VALUE: temperature_sensor_serial_number},
                   {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.TEMPERATURE_SENSOR_TYPE,
                   DataParticleKey.VALUE: temperature_sensor_type},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.CONDUCTIVITY_SENSOR_SERIAL_NUMBER,
                   DataParticleKey.VALUE: conductivity_sensor_serial_number},
                   {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.CONDUCTIVITY_SENSOR_TYPE,
                   DataParticleKey.VALUE: conductivity_sensor_type},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.PRESSURE_SENSOR_SERIAL_NUMBER,
                   DataParticleKey.VALUE: pressure_sensor_serial_number},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.PRESSURE_SENSOR_TYPE,
                   DataParticleKey.VALUE: pressure_sensor_type},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.VOLT0_SERIAL_NUMBER,
                   DataParticleKey.VALUE: volt0_serial_number},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.VOLT0_TYPE,
                   DataParticleKey.VALUE: volt0_type},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.VOLT1_SERIAL_NUMBER,
                   DataParticleKey.VALUE: volt1_serial_number},
                  {DataParticleKey.VALUE_ID: SBE16NOHardwareParticleKey.VOLT1_TYPE,
                   DataParticleKey.VALUE: volt1_type},
                  ]

        return result
    

class SBE16NOCalibrationParticleKey(BaseEnum):
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

class SBE16NOCalibrationParticle(SeaBirdParticle):
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
        return re.compile(SBE16NOCalibrationParticle.regex(), re.DOTALL)

    @staticmethod
    def resp_regex():
        pattern = r'(<CalibrationCoefficients.*?</CalibrationCoefficients>)'
        return pattern

    @staticmethod
    def resp_regex_compiled():
        return re.compile(SBE16NOCalibrationParticle.resp_regex(), re.DOTALL)

    def _map_param_to_xml_tag(self, parameter_name):
        map_param_to_tag = {SBE16NOCalibrationParticleKey.TEMP_SENSOR_SERIAL_NUMBER: "SerialNum",
                            SBE16NOCalibrationParticleKey.TEMP_CAL_DATE: "CalDate",
                            SBE16NOCalibrationParticleKey.TA0: "TA0",
                            SBE16NOCalibrationParticleKey.TA1: "TA1",
                            SBE16NOCalibrationParticleKey.TA2: "TA2",
                            SBE16NOCalibrationParticleKey.TA3: "TA3",
                            SBE16NOCalibrationParticleKey.TOFFSET: "TOFFSET",
                           
                            SBE16NOCalibrationParticleKey.COND_SENSOR_SERIAL_NUMBER: "SerialNum",
                            SBE16NOCalibrationParticleKey.COND_CAL_DATE: "CalDate",
                            SBE16NOCalibrationParticleKey.CONDG: "G",
                            SBE16NOCalibrationParticleKey.CONDH: "H",
                            SBE16NOCalibrationParticleKey.CONDI: "I",
                            SBE16NOCalibrationParticleKey.CONDJ: "J",
                            SBE16NOCalibrationParticleKey.CPCOR: "CPCOR",
                            SBE16NOCalibrationParticleKey.CTCOR: "CTCOR",
                            SBE16NOCalibrationParticleKey.CSLOPE: "CSLOPE",
        
                            SBE16NOCalibrationParticleKey.PRES_SERIAL_NUMBER: "SerialNum",
                            SBE16NOCalibrationParticleKey.PRES_CAL_DATE: "CalDate",
                            SBE16NOCalibrationParticleKey.PC1: "PC1",
                            SBE16NOCalibrationParticleKey.PC2: "PC2",
                            SBE16NOCalibrationParticleKey.PC3: "PC3",
                            SBE16NOCalibrationParticleKey.PD1: "PD1",
                            SBE16NOCalibrationParticleKey.PD2: "PD2",
                            SBE16NOCalibrationParticleKey.PT1: "PT1",
                            SBE16NOCalibrationParticleKey.PT2: "PT2",
                            SBE16NOCalibrationParticleKey.PT3: "PT3",
                            SBE16NOCalibrationParticleKey.PT4: "PT4",
                            SBE16NOCalibrationParticleKey.PSLOPE: "PSLOPE",
                            SBE16NOCalibrationParticleKey.POFFSET: "POFFSET",
                            SBE16NOCalibrationParticleKey.PRES_RANGE: "PRANGE",
        
                            SBE16NOCalibrationParticleKey.EXT_VOLT0_OFFSET: "OFFSET",
                            SBE16NOCalibrationParticleKey.EXT_VOLT0_SLOPE: "SLOPE",
                            SBE16NOCalibrationParticleKey.EXT_VOLT1_OFFSET: "OFFSET",
                            SBE16NOCalibrationParticleKey.EXT_VOLT1_SLOPE: "SLOPE",
                            SBE16NOCalibrationParticleKey.EXT_VOLT2_OFFSET: "OFFSET",
                            SBE16NOCalibrationParticleKey.EXT_VOLT2_SLOPE: "SLOPE",
                            SBE16NOCalibrationParticleKey.EXT_VOLT3_OFFSET: "OFFSET",
                            SBE16NOCalibrationParticleKey.EXT_VOLT3_SLOPE: "SLOPE",
                            SBE16NOCalibrationParticleKey.EXT_VOLT4_OFFSET: "OFFSET",
                            SBE16NOCalibrationParticleKey.EXT_VOLT4_SLOPE: "SLOPE",
                            SBE16NOCalibrationParticleKey.EXT_VOLT5_OFFSET: "OFFSET",
                            SBE16NOCalibrationParticleKey.EXT_VOLT5_SLOPE: "SLOPE",
         
                            SBE16NOCalibrationParticleKey.EXT_FREQ: "EXTFREQSF",
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
        match = SBE16NOCalibrationParticle.regex_compiled().match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed calibration data: [%s]" %
                                  self.raw_data)

        dom = parseString(self.raw_data)
        root = dom.documentElement
        log.debug("root.tagName = %s" %root.tagName)
        serial_number = int(root.getAttribute(SERIAL_NUMBER))
        result = [{DataParticleKey.VALUE_ID: SBE16NOCalibrationParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                 ]        
        
        calibration_elements = self._extract_xml_elements(root, CALIBRATION)
        for calibration in calibration_elements:
            id = calibration.getAttribute(ID)
            if id == TEMPERATURE_SENSOR_ID:
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.TEMP_SENSOR_SERIAL_NUMBER, int))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.TEMP_CAL_DATE, str))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.TA0))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.TA1))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.TA2))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.TA3))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.TOFFSET))
            elif id == CONDUCTIVITY_SENSOR_ID:
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.COND_SENSOR_SERIAL_NUMBER, int))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.COND_CAL_DATE, str))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.CONDG))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.CONDH))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.CONDI))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.CONDJ))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.CPCOR))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.CTCOR))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.CSLOPE))
            elif id == PRESSURE_SENSOR_ID:
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PRES_SERIAL_NUMBER, int))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PRES_CAL_DATE, str))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PC1))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PC2))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PC3))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PD1))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PD2))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PT1))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PT2))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PT3))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PT4))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PSLOPE))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.POFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.PRES_RANGE, self._float_to_int))
            elif id == VOLT0:
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_VOLT0_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_VOLT0_SLOPE))
            elif id == VOLT1:
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_VOLT1_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_VOLT1_SLOPE))
            elif id == VOLT2:
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_VOLT2_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_VOLT2_SLOPE))
            elif id == VOLT3:
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_VOLT3_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_VOLT3_SLOPE))
            elif id == VOLT4:
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_VOLT4_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_VOLT4_SLOPE))
            elif id == VOLT5:
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_VOLT5_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_VOLT5_SLOPE))
            elif id == EXTERNAL_FREQUENCY_CHANNEL:
                result.append(self._get_xml_parameter(calibration, SBE16NOCalibrationParticleKey.EXT_FREQ))

        return result


class SBE16NOConfigurationParticleKey(BaseEnum):
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
    

class SBE16NOConfigurationParticle(SeaBirdParticle):
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
        return re.compile(SBE16NOConfigurationParticle.regex(), re.DOTALL)

    @staticmethod
    def resp_regex():
        pattern = r'(<ConfigurationData.*?</ConfigurationData>)'
        return pattern

    @staticmethod
    def resp_regex_compiled():
        return re.compile(SBE16NOConfigurationParticle.resp_regex(), re.DOTALL)

    def _map_param_to_xml_tag(self, parameter_name):
        map_param_to_tag = {SBE16NOConfigurationParticleKey.SCANS_TO_AVERAGE: "ScansToAverage",
                            SBE16NOConfigurationParticleKey.MIN_COND_FREQ: "MinimumCondFreq",
                            SBE16NOConfigurationParticleKey.PUMP_DELAY: "PumpDelay",
                            SBE16NOConfigurationParticleKey.AUTO_RUN: "AutoRun",
                            SBE16NOConfigurationParticleKey.IGNORE_SWITCH: "IgnoreSwitch",

                            SBE16NOConfigurationParticleKey.BATTERY_TYPE: "Type",
                            SBE16NOConfigurationParticleKey.BATTERY_CUTOFF: "CutOff",

                            SBE16NOConfigurationParticleKey.EXT_VOLT_0: "ExtVolt0",
                            SBE16NOConfigurationParticleKey.EXT_VOLT_1: "ExtVolt1",
                            SBE16NOConfigurationParticleKey.EXT_VOLT_2: "ExtVolt2",
                            SBE16NOConfigurationParticleKey.EXT_VOLT_3: "ExtVolt3",
                            SBE16NOConfigurationParticleKey.EXT_VOLT_4: "ExtVolt4",
                            SBE16NOConfigurationParticleKey.EXT_VOLT_5: "ExtVolt5",
                            SBE16NOConfigurationParticleKey.SBE38: "SBE38",
                            SBE16NOConfigurationParticleKey.SBE63: "SBE63",
                            SBE16NOConfigurationParticleKey.WETLABS: "WETLABS",
                            SBE16NOConfigurationParticleKey.OPTODE: "OPTODE",
                            SBE16NOConfigurationParticleKey.GAS_TENSION_DEVICE: "GTD",

                            SBE16NOConfigurationParticleKey.ECHO_CHARACTERS: "EchoCharacters",
                            SBE16NOConfigurationParticleKey.OUTPUT_EXECUTED_TAG: "OutputExecutedTag",
                            SBE16NOConfigurationParticleKey.OUTPUT_FORMAT: "OutputFormat",
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
        match = SBE16NOConfigurationParticle.regex_compiled().match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed configuration data: [%s]" %
                                  self.raw_data)

        dom = parseString(self.raw_data)
        root = dom.documentElement
        log.debug("root.tagName = %s" %root.tagName)
        serial_number = int(root.getAttribute(SERIAL_NUMBER))
        result = [{DataParticleKey.VALUE_ID: SBE16NOConfigurationParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number}]
        result.append(self._get_xml_parameter(root, SBE16NOConfigurationParticleKey.ECHO_CHARACTERS, self.yesno2bool))
        result.append(self._get_xml_parameter(root, SBE16NOConfigurationParticleKey.OUTPUT_EXECUTED_TAG, self.yesno2bool))
        result.append(self._get_xml_parameter(root, SBE16NOConfigurationParticleKey.OUTPUT_FORMAT, str))

        element = self._extract_xml_elements(root, PROFILE_MODE)[0]
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.SCANS_TO_AVERAGE, int))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.MIN_COND_FREQ, int))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.PUMP_DELAY, int))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.AUTO_RUN, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.IGNORE_SWITCH, self.yesno2bool))

        element = self._extract_xml_elements(root, BATTERY)[0]
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.BATTERY_TYPE, str))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.BATTERY_CUTOFF))

        element = self._extract_xml_elements(root, DATA_CHANNELS)[0]
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.EXT_VOLT_0, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.EXT_VOLT_1, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.EXT_VOLT_2, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.EXT_VOLT_3, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.EXT_VOLT_4, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.EXT_VOLT_5, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.SBE38, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.WETLABS, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.OPTODE, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.SBE63, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16NOConfigurationParticleKey.GAS_TENSION_DEVICE, self.yesno2bool))

        return result


###############################################################################
# Seabird Electronics 16plus V2 NO Driver.
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

    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()


    ########################################################################
    # Protocol builder.
    ########################################################################
    ########################################################################
        # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = SBE16NOProtocol(Prompt, NEWLINE, self._driver_event)


###############################################################################
# Seabird Electronics 16plus V2 NO protocol.
###############################################################################

class SBE16NOProtocol(SBE19Protocol):
    """
    Instrument protocol class for SBE16 NO driver.
    Subclasses SBE16Protocol
    """
        
    def __init__(self, prompts, newline, driver_event):
        """
        SBE16Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The SBE16 newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        SBE19Protocol.__init__(self, prompts, newline, driver_event)
        
    @staticmethod
    def sieve_function(raw_data):
        """ The method that splits samples
        Over-ride sieve function to handle additional particles.
        """
        matchers = []
        return_list = []

        matchers.append(SBE19DataParticle.regex_compiled())
        matchers.append(SBE19HardwareParticle.regex_compiled())
        matchers.append(SBE16NOCalibrationParticle.regex_compiled())
        matchers.append(SBE19StatusParticle.regex_compiled())
        matchers.append(SBE16NOConfigurationParticle.regex_compiled())
        matchers.append(OptodeSettingsParticle.regex_compiled())
        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _got_chunk(self, chunk, timestamp):
        """
        Over-ride sieve function to handle additional particles.
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes. 
        """
        if not (self._extract_sample(SBE19HardwareParticle, SBE19HardwareParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE19DataParticle, SBE19DataParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE16NOCalibrationParticle, SBE16NOCalibrationParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE16NOConfigurationParticle, SBE16NOConfigurationParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE19StatusParticle, SBE19StatusParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(OptodeSettingsParticle, OptodeSettingsParticle.regex_compiled(), chunk, timestamp)):
            raise InstrumentProtocolException("Unhandled chunk %s" %chunk)

    ########################################################################
    # Command handlers.
    ########################################################################
    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None

        result = self._do_cmd_resp(Command.GET_SD, response_regex=SBE19StatusParticle.regex_compiled(),
                                    timeout=TIMEOUT)
        log.debug("_handler_command_acquire_status: GetSD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_HD, response_regex=SBE19HardwareParticle.regex_compiled(),
                                    timeout=TIMEOUT)
        log.debug("_handler_command_acquire_status: GetHD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_CD, response_regex=SBE16NOConfigurationParticle.regex_compiled(),
                                    timeout=TIMEOUT)
        log.debug("_handler_command_acquire_status: GetCD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_CC, response_regex=SBE16NOCalibrationParticle.regex_compiled(),
                                    timeout=TIMEOUT)
        log.debug("_handler_command_acquire_status: GetCC Response: %s", result)
        result += self._do_cmd_resp(Command.GET_EC, timeout=TIMEOUT)
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
            result += self._do_cmd_resp(Command.SEND_OPTODE, command, timeout=TIMEOUT)
            log.debug("_handler_command_acquire_status: SendOptode Response: %s", result)

        #restart the optode
        self._do_cmd_resp(Command.SEND_OPTODE, start_command, timeout=TIMEOUT)

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

        result = self._do_cmd_resp(Command.GET_SD, response_regex=SBE19StatusParticle.regex_compiled(),
                                    timeout=TIMEOUT)
        log.debug("_handler_autosample_acquire_status: GetSD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_HD, response_regex=SBE19HardwareParticle.regex_compiled(),
                                    timeout=TIMEOUT)
        log.debug("_handler_autosample_acquire_status: GetHD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_CD, response_regex=SBE16NOConfigurationParticle.regex_compiled(),
                                    timeout=TIMEOUT)
        log.debug("_handler_autosample_acquire_status: GetCD Response: %s", result)
        result += self._do_cmd_resp(Command.GET_CC, response_regex=SBE16NOCalibrationParticle.regex_compiled(),
                                    timeout=TIMEOUT)
        log.debug("_handler_autosample_acquire_status: GetCC Response: %s", result)
        result += self._do_cmd_resp(Command.GET_EC, timeout=TIMEOUT)
        log.debug("_handler_autosample_acquire_status: GetEC Response: %s", result)

        #Reset the event counter right after getEC
        self._do_cmd_no_resp(Command.RESET_EC)

        return (next_state, (next_agent_state, result))


    ########################################################################
    # response handlers.
    ########################################################################

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

        if not SBE16NOConfigurationParticle.resp_regex_compiled().search(response):
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

        if not SBE16NOCalibrationParticle.resp_regex_compiled().search(response):
            log.error('_validate_GetCC_response: GetCC command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetCC command not recognized: %s.' % response)

        return response



    ########################################################################
    # Private helpers.
    ########################################################################

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with SBE19 parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.

        self._param_dict.add(Parameter.DATE_TIME,
                             r'SBE 19plus V ([\w.]+) +SERIAL NO. (\d+) +(\d{2} [a-zA-Z]{3,4} \d{4} +[\d:]+)',
                             lambda match : string.upper(match.group(3)),
                             self._date_time_string_to_numeric,
                             type=ParameterDictType.STRING,
                             display_name="Date/Time",
                             #expiration=0,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.LOGGING,
                             r'status = (not )?logging',
                             lambda match : False if (match.group(1)) else True,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Is Logging",
                             #expiration=0,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self._param_dict.add(Parameter.PTYPE,
                             r'pressure sensor = ([\w\s]+),',
                             self._pressure_sensor_to_int,
                             str,
                             type=ParameterDictType.INT,
                             display_name="Pressure Sensor Type",
                             startup_param = True,
                             direct_access = True,
                             default_value = 3,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.VOLT0,
                             r'Ext Volt 0 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 0",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.VOLT1,
                             r'Ext Volt 1 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 1",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.VOLT2,
                             r'Ext Volt 2 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 2",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.VOLT3,
                             r'Ext Volt 3 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 3",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.VOLT4,
                             r'Ext Volt 4 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 4",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.VOLT5,
                             r'Ext Volt 5 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 5",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.SBE38,
                             r'SBE 38 = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="SBE38 Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.WETLABS,
                             r'WETLABS = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Enable Wetlabs sensor",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.GTD,
                             r'Gas Tension Device = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="GTD Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.DUAL_GTD,
                             r'Gas Tension Device = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Dual GTD Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.SBE63,
                             r'SBE 63 = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="SBE63 Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.OPTODE,
                             r'OPTODE = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Optode Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.OUTPUT_FORMAT,
                             r'output format = (raw HEX)',
                             self._output_format_string_2_int,
                             int,
                             type=ParameterDictType.INT,
                             display_name="Output Format",
                             startup_param = True,
                             direct_access = True,
                             default_value = 0,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.NUM_AVG_SAMPLES,
                             r'number of scans to average = ([\d]+)',
                             lambda match : int(match.group(1)),
                             str,
                             type=ParameterDictType.INT,
                             display_name="Scans To Average",
                             startup_param = True,
                             direct_access = False,
                             default_value = 4,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.MIN_COND_FREQ,
                             r'minimum cond freq = ([\d]+)',
                             lambda match : int(match.group(1)),
                             str,
                             type=ParameterDictType.INT,
                             display_name="Minimum Conductivity Frequency",
                             startup_param = True,
                             direct_access = False,
                             default_value = 500,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.PUMP_DELAY,
                             r'pump delay = ([\d]+) sec',
                             lambda match : int(match.group(1)),
                             str,
                             type=ParameterDictType.INT,
                             display_name="Pump Delay",
                             startup_param = True,
                             direct_access = False,
                             default_value = 60,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.AUTO_RUN,
                             r'autorun = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Auto Run",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.IGNORE_SWITCH,
                             r'ignore magnetic switch = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Ignore Switch",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.IMMUTABLE)