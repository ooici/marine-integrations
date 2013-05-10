"""
@package mi.instrument.seabird.sbe16plus_v2.ooicore.driver
@file mi/instrument/seabird/sbe16plus_v2/ooicore/driver.py
@author David Everett 
@brief Driver class for sbe16plus V2 CTD instrument.
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

# MI logger
from mi.core.log import get_logger ; log = get_logger()

from xml.dom.minidom import parseString

import re

import mi.instrument.seabird.sbe16plus_v2.driver as sbe16plus_driver

import mi.instrument.seabird.driver as seabird_driver

from mi.core.instrument.data_particle import DataParticleKey, \
                                             CommonDataParticleType

from mi.core.exceptions import InstrumentProtocolException

from mi.core.common import BaseEnum

from mi.core.exceptions import SampleException, \
                               InstrumentProtocolException

from mi.core.instrument.protocol_param_dict import ParameterDictVisibility, \
                                                   ParameterDictType

class Command(BaseEnum):
    GETSD = 'GetSD'
    GETHD = 'GetHD'
    GETCD = 'GetCD'
    GETCC = 'GetCC'

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    CTD_PARSED = 'ctdbp_no_sample'
    DEVICE_STATUS = 'ctdbp_no_status'
    DEVICE_CALIBRATION = 'ctdbp_no_calibration_coefficients'
    DEVICE_HARDWARE = 'ctdbp_no_hardware'
    DEVICE_CONFIGURATION = 'ctdbp_no_configuration'

###############################################################################
# Particles
###############################################################################

class SBE16CalibrationDataParticleKey(BaseEnum):
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

class SBE16CalibrationDataParticle(seabird_driver.SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_CALIBRATION

    @staticmethod
    def regex():
        pattern = r'<CalibrationCoefficients.*?</CalibrationCoefficients>' + seabird_driver.NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE16CalibrationDataParticle.regex(), re.DOTALL)
    
    def _map_param_to_xml_tag(self, parameter_name):
        map_param_to_tag = {SBE16CalibrationDataParticleKey.TEMP_SENSOR_SERIAL_NUMBER: "SerialNum",
                            SBE16CalibrationDataParticleKey.TEMP_CAL_DATE: "CalDate",
                            SBE16CalibrationDataParticleKey.TA0: "TA0",
                            SBE16CalibrationDataParticleKey.TA1: "TA1",
                            SBE16CalibrationDataParticleKey.TA2: "TA2",
                            SBE16CalibrationDataParticleKey.TA3: "TA3",
                            SBE16CalibrationDataParticleKey.TOFFSET: "TOFFSET",
                           
                            SBE16CalibrationDataParticleKey.COND_SENSOR_SERIAL_NUMBER: "SerialNum",
                            SBE16CalibrationDataParticleKey.COND_CAL_DATE: "CalDate",
                            SBE16CalibrationDataParticleKey.CONDG: "G",
                            SBE16CalibrationDataParticleKey.CONDH: "H",
                            SBE16CalibrationDataParticleKey.CONDI: "I",
                            SBE16CalibrationDataParticleKey.CONDJ: "J",
                            SBE16CalibrationDataParticleKey.CPCOR: "CPCOR",
                            SBE16CalibrationDataParticleKey.CTCOR: "CTCOR",
                            SBE16CalibrationDataParticleKey.CSLOPE: "CSLOPE",
        
                            SBE16CalibrationDataParticleKey.PRES_SERIAL_NUMBER: "SerialNum",
                            SBE16CalibrationDataParticleKey.PRES_CAL_DATE: "CalDate",
                            SBE16CalibrationDataParticleKey.PC1: "PC1",
                            SBE16CalibrationDataParticleKey.PC2: "PC2",
                            SBE16CalibrationDataParticleKey.PC3: "PC3",
                            SBE16CalibrationDataParticleKey.PD1: "PD1",
                            SBE16CalibrationDataParticleKey.PD2: "PD2",
                            SBE16CalibrationDataParticleKey.PT1: "PT1",
                            SBE16CalibrationDataParticleKey.PT2: "PT2",
                            SBE16CalibrationDataParticleKey.PT3: "PT3",
                            SBE16CalibrationDataParticleKey.PT4: "PT4",
                            SBE16CalibrationDataParticleKey.PSLOPE: "PSLOPE",
                            SBE16CalibrationDataParticleKey.POFFSET: "POFFSET",
                            SBE16CalibrationDataParticleKey.PRES_RANGE: "PRANGE",
        
                            SBE16CalibrationDataParticleKey.EXT_VOLT0_OFFSET: "OFFSET",
                            SBE16CalibrationDataParticleKey.EXT_VOLT0_SLOPE: "SLOPE",
                            SBE16CalibrationDataParticleKey.EXT_VOLT1_OFFSET: "OFFSET",
                            SBE16CalibrationDataParticleKey.EXT_VOLT1_SLOPE: "SLOPE",
                            SBE16CalibrationDataParticleKey.EXT_VOLT2_OFFSET: "OFFSET",
                            SBE16CalibrationDataParticleKey.EXT_VOLT2_SLOPE: "SLOPE",
                            SBE16CalibrationDataParticleKey.EXT_VOLT3_OFFSET: "OFFSET",
                            SBE16CalibrationDataParticleKey.EXT_VOLT3_SLOPE: "SLOPE",
                            SBE16CalibrationDataParticleKey.EXT_VOLT4_OFFSET: "OFFSET",
                            SBE16CalibrationDataParticleKey.EXT_VOLT4_SLOPE: "SLOPE",
                            SBE16CalibrationDataParticleKey.EXT_VOLT5_OFFSET: "OFFSET",
                            SBE16CalibrationDataParticleKey.EXT_VOLT5_SLOPE: "SLOPE",
         
                            SBE16CalibrationDataParticleKey.EXT_FREQ: "EXTFREQSF",
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
        match = SBE16CalibrationDataParticle.regex_compiled().match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed calibration data: [%s]" %
                                  self.raw_data)

        dom = parseString(self.raw_data)
        root = dom.documentElement
        log.debug("root.tagName = %s" %root.tagName)
        serial_number = int(root.getAttribute(SERIAL_NUMBER))
        result = [{DataParticleKey.VALUE_ID: SBE16CalibrationDataParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                 ]        
        
        calibration_elements = self._extract_xml_elements(root, CALIBRATION)
        for calibration in calibration_elements:
            id = calibration.getAttribute(ID)
            if id == TEMPERATURE_SENSOR_ID:
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.TEMP_SENSOR_SERIAL_NUMBER, int))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.TEMP_CAL_DATE, str))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.TA0))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.TA1))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.TA2))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.TA3))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.TOFFSET))
            elif id == CONDUCTIVITY_SENSOR_ID:
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.COND_SENSOR_SERIAL_NUMBER, int))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.COND_CAL_DATE, str))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.CONDG))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.CONDH))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.CONDI))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.CONDJ))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.CPCOR))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.CTCOR))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.CSLOPE))
            elif id == PRESSURE_SENSOR_ID:
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PRES_SERIAL_NUMBER, int))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PRES_CAL_DATE, str))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PC1))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PC2))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PC3))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PD1))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PD2))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PT1))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PT2))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PT3))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PT4))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PSLOPE))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.POFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.PRES_RANGE, self._float_to_int))
            elif id == VOLT0:
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_VOLT0_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_VOLT0_SLOPE))
            elif id == VOLT1:
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_VOLT1_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_VOLT1_SLOPE))
            elif id == VOLT2:
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_VOLT2_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_VOLT2_SLOPE))
            elif id == VOLT3:
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_VOLT3_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_VOLT3_SLOPE))
            elif id == VOLT4:
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_VOLT4_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_VOLT4_SLOPE))
            elif id == VOLT5:
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_VOLT5_OFFSET))
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_VOLT5_SLOPE))
            elif id == EXTERNAL_FREQUENCY_CHANNEL:
                result.append(self._get_xml_parameter(calibration, SBE16CalibrationDataParticleKey.EXT_FREQ))

        return result

class SBE16StatusDataParticleKey(BaseEnum):
    SERIAL_NUMBER = "serial_number"

    DATE_TIME = "date_time_string"
    LOGGING_STATUS = "logging_status"
    NUMBER_OF_EVENTS = "num_events"
    
    BATTERY_VOLTAGE_MAIN = "battery_voltage_main"
    BATTERY_VOLTAGE_LITHIUM = "battery_voltage_lithium"
    OPERATIONAL_CURRENT = "operational_current"
    PUMP_CURRENT = "pump_current"
    EXT_V01_CURRENT = "ext_v01_current"
    SERIAL_CURRENT = "serial_current"
    
    MEMMORY_FREE = "mem_free"
    NUMBER_OF_SAMPLES = "numm_samples"
    SAMPLES_FREE = "samples_free"
    SAMPLE_LENGTH = "sample_length"
    HEADERS = "headers"

class SBE16StatusDataParticle(seabird_driver.SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_STATUS

    @staticmethod
    def regex():
        pattern = r'<StatusData.*?</StatusData>' + seabird_driver.NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE16StatusDataParticle.regex(), re.DOTALL)
    
    def _map_param_to_xml_tag(self, parameter_name):
        map_param_to_tag = {SBE16StatusDataParticleKey.BATTERY_VOLTAGE_MAIN: "vMain",
                            SBE16StatusDataParticleKey.BATTERY_VOLTAGE_LITHIUM: "vLith",
                            SBE16StatusDataParticleKey.OPERATIONAL_CURRENT: "iMain",
                            SBE16StatusDataParticleKey.PUMP_CURRENT: "iPump",
                            SBE16StatusDataParticleKey.EXT_V01_CURRENT: "iExt01",
                            SBE16StatusDataParticleKey.SERIAL_CURRENT: "iSerial",
                            
                            SBE16StatusDataParticleKey.MEMMORY_FREE: "Bytes",
                            SBE16StatusDataParticleKey.NUMBER_OF_SAMPLES: "Samples",
                            SBE16StatusDataParticleKey.SAMPLES_FREE: "SamplesFree",
                            SBE16StatusDataParticleKey.SAMPLE_LENGTH: "SampleLength",
                            SBE16StatusDataParticleKey.HEADERS: "Headers",
                           }
        return map_param_to_tag[parameter_name]
   
    def _build_parsed_values(self):
        """
        Parse the output of the getCC command
        @throws SampleException If there is a problem with sample creation
        """

        SERIAL_NUMBER = "SerialNumber"
        DATE_TIME = "DateTime"
        LOGGING_STATE = "LoggingState"
        EVENT_SUMMARY = "EventSummary"
        NUMBER_OF_EVENTS = "numEvents"
        POWER = "Power"
        MEMORY_SUMMERY = "MemorySummary"

        # check to make sure there is a correct match before continuing
        match = SBE16StatusDataParticle.regex_compiled().match(self.raw_data)
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
        result = [{DataParticleKey.VALUE_ID: SBE16StatusDataParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: SBE16StatusDataParticleKey.DATE_TIME,
                   DataParticleKey.VALUE: date_time},
                  {DataParticleKey.VALUE_ID: SBE16StatusDataParticleKey.LOGGING_STATUS,
                   DataParticleKey.VALUE: logging_status},
                  {DataParticleKey.VALUE_ID: SBE16StatusDataParticleKey.NUMBER_OF_EVENTS,
                   DataParticleKey.VALUE: number_of_events},
                 ]        
        
        element = self._extract_xml_elements(root, POWER)[0]
        result.append(self._get_xml_parameter(element, SBE16StatusDataParticleKey.BATTERY_VOLTAGE_MAIN))
        result.append(self._get_xml_parameter(element, SBE16StatusDataParticleKey.BATTERY_VOLTAGE_LITHIUM))
        result.append(self._get_xml_parameter(element, SBE16StatusDataParticleKey.OPERATIONAL_CURRENT))
        result.append(self._get_xml_parameter(element, SBE16StatusDataParticleKey.PUMP_CURRENT))
        result.append(self._get_xml_parameter(element, SBE16StatusDataParticleKey.EXT_V01_CURRENT))
        result.append(self._get_xml_parameter(element, SBE16StatusDataParticleKey.SERIAL_CURRENT))

        element = self._extract_xml_elements(root, MEMORY_SUMMERY)[0]
        result.append(self._get_xml_parameter(element, SBE16StatusDataParticleKey.MEMMORY_FREE, int))
        result.append(self._get_xml_parameter(element, SBE16StatusDataParticleKey.NUMBER_OF_SAMPLES, int))
        result.append(self._get_xml_parameter(element, SBE16StatusDataParticleKey.SAMPLES_FREE, int))
        result.append(self._get_xml_parameter(element, SBE16StatusDataParticleKey.SAMPLE_LENGTH, int))
        result.append(self._get_xml_parameter(element, SBE16StatusDataParticleKey.HEADERS, int))

        return result

class SBE16ConfigurationDataParticleKey(BaseEnum):
    SERIAL_NUMBER = "serial_number"

    SAMPLE_INTERVAL = "sample_interval"
    MEASUREMENTS_PER_SAMPLE= " measurements_per_sample"
    PAROS_INTEGRATION_TIME = " paros_integration"
    PUMP_MODE = "pump_mode"
    DELAY_BEFORE_SAMPLING = "delay_before_sampling"
    DELAY_AFTER_SAMPLING = "delay_after_sampling"
    TRANSMIT_REAL_TIME = "tx_real_time"
    
    BATTERY_CUTOFF = "battery_cutoff"
    
    EXT_VOLT_0 = "ext_volt_0"
    EXT_VOLT_1 = "ext_volt_1"
    EXT_VOLT_2 = "ext_volt_2"
    EXT_VOLT_3 = "ext_volt_3"
    EXT_VOLT_4 = "ext_volt_4"
    EXT_VOLT_5 = "ext_volt_5"
    SBE38 = "sbe38"
    SBE50 = "sbe50"
    WETLABS = "wetlabs"
    OPTODE = "optode"
    GAS_TENSION_DEVICE = "gas_tension_device"
    
    ECHO_CHARACTERS = "echo_characters"
    OUTPUT_EXECUTED_TAG = "output_executed_tag"
    OUTPUT_FORMAT = "output_format"
    SERIAL_SYNC_MODE = "serial_sync_mode"
    

class SBE16ConfigurationDataParticle(seabird_driver.SeaBirdParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    _data_particle_type = DataParticleType.DEVICE_CONFIGURATION

    @staticmethod
    def regex():
        pattern = r'<ConfigurationData.*?</ConfigurationData>' + seabird_driver.NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        return re.compile(SBE16ConfigurationDataParticle.regex(), re.DOTALL)
    
    def _map_param_to_xml_tag(self, parameter_name):
        map_param_to_tag = {SBE16ConfigurationDataParticleKey.SAMPLE_INTERVAL: "SampleInterval",
                            SBE16ConfigurationDataParticleKey.MEASUREMENTS_PER_SAMPLE: "MeasurementsPerSample",
                            SBE16ConfigurationDataParticleKey.PAROS_INTEGRATION_TIME: "ParosIntegrationTime",
                            SBE16ConfigurationDataParticleKey.PUMP_MODE: "Pump",
                            SBE16ConfigurationDataParticleKey.DELAY_BEFORE_SAMPLING: "DelayBeforeSampling",
                            SBE16ConfigurationDataParticleKey.DELAY_AFTER_SAMPLING: "DelayAfterSampling",
                            SBE16ConfigurationDataParticleKey.TRANSMIT_REAL_TIME: "TransmitRealTime",
                            
                            SBE16ConfigurationDataParticleKey.BATTERY_CUTOFF: "CutOff",

                            SBE16ConfigurationDataParticleKey.EXT_VOLT_0: "ExtVolt0",
                            SBE16ConfigurationDataParticleKey.EXT_VOLT_1: "ExtVolt1",
                            SBE16ConfigurationDataParticleKey.EXT_VOLT_2: "ExtVolt2",
                            SBE16ConfigurationDataParticleKey.EXT_VOLT_3: "ExtVolt3",
                            SBE16ConfigurationDataParticleKey.EXT_VOLT_4: "ExtVolt4",
                            SBE16ConfigurationDataParticleKey.EXT_VOLT_5: "ExtVolt5",
                            SBE16ConfigurationDataParticleKey.SBE38: "SBE38",
                            SBE16ConfigurationDataParticleKey.SBE50: "SBE50",
                            SBE16ConfigurationDataParticleKey.WETLABS: "WETLABS",
                            SBE16ConfigurationDataParticleKey.OPTODE: "OPTODE",
                            SBE16ConfigurationDataParticleKey.GAS_TENSION_DEVICE: "GTD",
                            
                            SBE16ConfigurationDataParticleKey.ECHO_CHARACTERS: "EchoCharacters",
                            SBE16ConfigurationDataParticleKey.OUTPUT_EXECUTED_TAG: "OutputExecutedTag",
                            SBE16ConfigurationDataParticleKey.OUTPUT_FORMAT: "OutputFormat",
                            SBE16ConfigurationDataParticleKey.SERIAL_SYNC_MODE: "SerialLineSync",
                           }
        return map_param_to_tag[parameter_name]

    def _build_parsed_values(self):
        """
        Parse the output of the getCC command
        @throws SampleException If there is a problem with sample creation
        """

        SERIAL_NUMBER = "SerialNumber"
        SAMPLING_PARAMETERS = "SamplingParameters"
        BATTERY = "Battery"
        DATA_CHANNELS = "DataChannels"

        # check to make sure there is a correct match before continuing
        match = SBE16ConfigurationDataParticle.regex_compiled().match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed configuration data: [%s]" %
                                  self.raw_data)

        dom = parseString(self.raw_data)
        root = dom.documentElement
        log.debug("root.tagName = %s" %root.tagName)
        serial_number = int(root.getAttribute(SERIAL_NUMBER))
        result = [{DataParticleKey.VALUE_ID: SBE16StatusDataParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number}]
        result.append(self._get_xml_parameter(root, SBE16ConfigurationDataParticleKey.ECHO_CHARACTERS, self.yesno2bool))
        result.append(self._get_xml_parameter(root, SBE16ConfigurationDataParticleKey.OUTPUT_EXECUTED_TAG, self.yesno2bool))
        result.append(self._get_xml_parameter(root, SBE16ConfigurationDataParticleKey.OUTPUT_FORMAT, str))
        result.append(self._get_xml_parameter(root, SBE16ConfigurationDataParticleKey.SERIAL_SYNC_MODE, self.yesno2bool))

        element = self._extract_xml_elements(root, SAMPLING_PARAMETERS)[0]
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.SAMPLE_INTERVAL, int))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.MEASUREMENTS_PER_SAMPLE, int))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.PAROS_INTEGRATION_TIME))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.PUMP_MODE, str))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.DELAY_BEFORE_SAMPLING))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.DELAY_AFTER_SAMPLING))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.TRANSMIT_REAL_TIME, self.yesno2bool))

        element = self._extract_xml_elements(root, BATTERY)[0]
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.BATTERY_CUTOFF))

        element = self._extract_xml_elements(root, DATA_CHANNELS)[0]
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.EXT_VOLT_0, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.EXT_VOLT_1, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.EXT_VOLT_2, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.EXT_VOLT_3, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.EXT_VOLT_4, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.EXT_VOLT_5, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.SBE38, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.SBE50, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.WETLABS, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.OPTODE, self.yesno2bool))
        result.append(self._get_xml_parameter(element, SBE16ConfigurationDataParticleKey.GAS_TENSION_DEVICE, self.yesno2bool))

        return result

class SBE16HardwareDataParticleKey(BaseEnum):
    SERIAL_NUMBER = "serial_number"
    FIRMWARE_VERSION = "firmware_version"
    FIRMWARE_DATE = "firmware_date"
    COMMAND_SET_VERSION = "command_set_version"
    PCB_SERIAL_NUMBER = "pcb_serial_number"
    ASSEMBLY_NUMBER = "assembly_number"
    MANUFATURE_DATE = "manufacture_date"
    TEMPERATURE_SENSOR_SERIAL_NUMBER = 'temperature_sensor_serial_number'
    CONDUCTIVITY_SENSOR_SERIAL_NUMBER = 'conductivity_sensor_serial_number'
    PRESSURE_SENSOR_TYPE = 'pressure_sensor_type'
    QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER = 'quartz_pressure_sensor_serial_number'

class SBE16HardwareDataParticle(seabird_driver.SeaBirdParticle):
    
    _data_particle_type = DataParticleType.DEVICE_HARDWARE

    @staticmethod
    def regex():
        """
        Regular expression to match a getHD response pattern
        @return: regex string
        """
        pattern = r'<HardwareData.*?</HardwareData>' + seabird_driver.NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(SBE16HardwareDataParticle.regex(), re.DOTALL)

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
        MANUFATURE_DATE = "MfgDate"
        INTERNAL_SENSORS = "InternalSensors"
        TEMPERATURE_SENSOR_ID = "Main Temperature"
        CONDUCTIVITY_SENSOR_ID = "Main Conductivity"
        PRESSURE_SENSOR_ID = "Main Pressure"
        
        # check to make sure there is a correct match before continuing
        match = SBE16HardwareDataParticle.regex_compiled().match(self.raw_data)
        if not match:
            raise SampleException("No regex match of parsed hardware data: [%s]" %
                                  self.raw_data)
        
        dom = parseString(self.raw_data)
        root = dom.documentElement
        log.debug("root.tagName = %s" %root.tagName)
        serial_number = int(root.getAttribute(SERIAL_NUMBER))
        
        firmware_version = self._extract_xml_element_value(root, FIRMWARE_VERSION)
        firmware_date = self._extract_xml_element_value(root, FIRMWARE_DATE)
        command_set_version = self._extract_xml_element_value(root, COMMAND_SET_VERSION)
        manufacture_date = self._extract_xml_element_value(root, MANUFATURE_DATE)
        
        pcb_assembly_elements = self._extract_xml_elements(root, PCB_ASSEMBLY)
        pcb_serial_number = []
        pcb_assembly = []
        for assembly in pcb_assembly_elements:
            pcb_serial_number.append(assembly.getAttribute(PCB_SERIAL_NUMBER))
            pcb_assembly.append(assembly.getAttribute(ASSEMBLY_NUMBER))
        
        internal_sensors_element = self._extract_xml_elements(root, INTERNAL_SENSORS)[0]
        sensors = self._extract_xml_elements(internal_sensors_element, SENSOR)
        for sensor in sensors:
            sensor_id = sensor.getAttribute(ID)
            if sensor_id == TEMPERATURE_SENSOR_ID:
                temperature_sensor_serial_number = int(self._extract_xml_element_value(sensor, SERIAL_NUMBER))
            elif sensor_id == CONDUCTIVITY_SENSOR_ID:
                conductivity_sensor_serial_number = int(self._extract_xml_element_value(sensor, SERIAL_NUMBER))
            elif sensor_id == PRESSURE_SENSOR_ID:
                pressure_sensor_serial_number = int(self._extract_xml_element_value(sensor, SERIAL_NUMBER))
                pressure_sensor_type = self._extract_xml_element_value(sensor, TYPE)                

        result = [{DataParticleKey.VALUE_ID: SBE16HardwareDataParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: SBE16HardwareDataParticleKey.FIRMWARE_VERSION,
                   DataParticleKey.VALUE: firmware_version},
                  {DataParticleKey.VALUE_ID: SBE16HardwareDataParticleKey.FIRMWARE_DATE,
                   DataParticleKey.VALUE: firmware_date},
                  {DataParticleKey.VALUE_ID: SBE16HardwareDataParticleKey.COMMAND_SET_VERSION,
                   DataParticleKey.VALUE: command_set_version},
                  {DataParticleKey.VALUE_ID: SBE16HardwareDataParticleKey.MANUFATURE_DATE,
                   DataParticleKey.VALUE: manufacture_date},
                  {DataParticleKey.VALUE_ID: SBE16HardwareDataParticleKey.PCB_SERIAL_NUMBER,
                   DataParticleKey.VALUE: pcb_serial_number},
                  {DataParticleKey.VALUE_ID: SBE16HardwareDataParticleKey.ASSEMBLY_NUMBER,
                   DataParticleKey.VALUE: pcb_assembly},
                  {DataParticleKey.VALUE_ID: SBE16HardwareDataParticleKey.TEMPERATURE_SENSOR_SERIAL_NUMBER,
                   DataParticleKey.VALUE: temperature_sensor_serial_number},
                  {DataParticleKey.VALUE_ID: SBE16HardwareDataParticleKey.CONDUCTIVITY_SENSOR_SERIAL_NUMBER,
                   DataParticleKey.VALUE: conductivity_sensor_serial_number},
                  {DataParticleKey.VALUE_ID: SBE16HardwareDataParticleKey.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER,
                   DataParticleKey.VALUE: pressure_sensor_serial_number},
                  {DataParticleKey.VALUE_ID: SBE16HardwareDataParticleKey.PRESSURE_SENSOR_TYPE,
                   DataParticleKey.VALUE: pressure_sensor_type},
                  ]
        
        return result


class SBE16NoDataParticleKey(sbe16plus_driver.SBE16DataParticleKey):
    OXYGEN = "oxygen"
    OXY_CALPHASE = "oxy_calphase"
    OXY_TEMP = "oxy_temp"
    

class SBE16NoDataParticle(sbe16plus_driver.SBE16DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Format:
       #ttttttccccccppppppvvvvvvvvvvvvoooooossssssss

       Temperature = tttttt 
       Conductivity = cccccc 
       quartz pressure = pppppp
       quartz pressure temperature compensation = vvvv 
       First external voltage = vvvv
       Second external voltage = vvvv
       Oxygen = oooooo
       Time = ssssssss 
    """
    _data_particle_type = DataParticleType.CTD_PARSED

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        #ttttttccccccppppppvvvvvvvvvvvvoooooossssssss
        pattern = r'#? *' # patter may or may not start with a '
        pattern += r'[0-9A-F]{22}' # temperature, conductivity, pressure, pressure temp
        pattern += r'([0-9A-F]{4})' # volt0, calibrated phase
        pattern += r'([0-9A-F]{4})' # volt1, oxygen temperature
        pattern += r'([0-9A-F]{6})' # oxygen 
        pattern += r'[0-9A-F]{8}' # time
        pattern += seabird_driver.NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(SBE16NoDataParticle.regex())

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = SBE16NoDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)
            
        base_class_result = sbe16plus_driver.SBE16DataParticle._build_parsed_values(self)
        
        try:
            cal_phase = self.hex2value(match.group(1))
            oxygen_temperature = self.hex2value(match.group(2))
            oxygen = self.hex2value(match.group(3))
        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)
            
        base_class_result.append({DataParticleKey.VALUE_ID: SBE16NoDataParticleKey.OXY_CALPHASE,
                                  DataParticleKey.VALUE: cal_phase})
        base_class_result.append({DataParticleKey.VALUE_ID: SBE16NoDataParticleKey.OXY_TEMP,
                                  DataParticleKey.VALUE: oxygen_temperature})
        base_class_result.append({DataParticleKey.VALUE_ID: SBE16NoDataParticleKey.OXYGEN,
                                  DataParticleKey.VALUE: oxygen})
                
        return base_class_result

###############################################################################
# Seabird Electronics 16plus V2 NO Driver.
###############################################################################

class InstrumentDriver(sbe16plus_driver.SBE16InstrumentDriver):
    
    ########################################################################
        # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = SBE16_NO_Protocol(sbe16plus_driver.Prompt, seabird_driver.NEWLINE, self._driver_event)


###############################################################################
# Seabird Electronics 16plus V2 NO protocol.
###############################################################################

class SBE16_NO_Protocol(sbe16plus_driver.SBE16Protocol):
    """
    Instrument protocol class for SBE16 NO driver.
    Subclasses SBE16Protocol
    """
    
    sbe16plus_driver.Parameter.PAROS_INTEGRATION = "paros_integration"
        
    def __init__(self, prompts, newline, driver_event):
        """
        SBE16Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The SBE16 newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        sbe16plus_driver.SBE16Protocol.__init__(self, prompts, newline, driver_event)

        # Add build handlers for NO device commands.
        self._add_build_handler(Command.GETSD, self._build_simple_command)
        self._add_build_handler(Command.GETHD, self._build_simple_command)
        self._add_build_handler(Command.GETCD, self._build_simple_command)
        self._add_build_handler(Command.GETCC, self._build_simple_command)

        # Add response handlers for NO device commands.
        # these are here to ensure that correct responses to the commands are received before the next command is sent
        self._add_response_handler(Command.GETSD, self._validate_GetSD_response)  
        self._add_response_handler(Command.GETHD, self._validate_GetHD_response)  
        self._add_response_handler(Command.GETCD, self._validate_GetCD_response)  
        self._add_response_handler(Command.GETCC, self._validate_GetCC_response)  
        
    @staticmethod
    def sieve_function(raw_data):
        """ The method that splits samples
        Over-ride sieve function to handle additional particles.
        """
        matchers = []
        return_list = []

        """
        matchers.append(SBE16StatusParticle.regex_compiled())
        matchers.append(SBE16CalibrationParticle.regex_compiled())
        """
        matchers.append(SBE16NoDataParticle.regex_compiled())
        matchers.append(SBE16HardwareDataParticle.regex_compiled())
        matchers.append(SBE16CalibrationDataParticle.regex_compiled())
        matchers.append(SBE16StatusDataParticle.regex_compiled())
        matchers.append(SBE16ConfigurationDataParticle.regex_compiled())

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
        if not (self._extract_sample(SBE16HardwareDataParticle, SBE16HardwareDataParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE16NoDataParticle, SBE16NoDataParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE16CalibrationDataParticle, SBE16CalibrationDataParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE16ConfigurationDataParticle, SBE16ConfigurationDataParticle.regex_compiled(), chunk, timestamp) or
                self._extract_sample(SBE16StatusDataParticle, SBE16StatusDataParticle.regex_compiled(), chunk, timestamp)):
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

        result = self._do_cmd_resp(Command.GETSD, timeout=sbe16plus_driver.TIMEOUT, expected_prompt=sbe16plus_driver.Prompt.EXECUTED)
        log.debug("_handler_command_acquire_status: GetSD Response: %s", result)
        result = self._do_cmd_resp(Command.GETHD, timeout=sbe16plus_driver.TIMEOUT, expected_prompt=sbe16plus_driver.Prompt.EXECUTED)
        log.debug("_handler_command_acquire_status: GetHD Response: %s", result)
        result = self._do_cmd_resp(Command.GETCD, timeout=sbe16plus_driver.TIMEOUT, expected_prompt=sbe16plus_driver.Prompt.EXECUTED)
        log.debug("_handler_command_acquire_status: GetCD Response: %s", result)
        result = self._do_cmd_resp(Command.GETCC, timeout=sbe16plus_driver.TIMEOUT, expected_prompt=sbe16plus_driver.Prompt.EXECUTED)
        log.debug("_handler_command_acquire_status: GetCC Response: %s", result)

        return (next_state, (next_agent_state, result))

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

        kwargs['timeout'] = sbe16plus_driver.TIMEOUT
        result = self._do_cmd_resp(Command.GETCC, expected_prompt=sbe16plus_driver.Prompt.EXECUTED, *args, **kwargs)
        log.debug("_handler_command_get_configuration: GetCC Response: %s", result)

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_acquire_status(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None

        # When in autosample this command requires two wakeups to get to the right prompt
        prompt = self._wakeup(timeout=sbe16plus_driver.WAKEUP_TIMEOUT, delay=0.3)
        prompt = self._wakeup(timeout=sbe16plus_driver.WAKEUP_TIMEOUT, delay=0.3)

        result = self._do_cmd_resp(Command.GETSD, timeout=sbe16plus_driver.TIMEOUT, expected_prompt=sbe16plus_driver.Prompt.EXECUTED)
        log.debug("_handler_autosample_acquire_status: GetSD Response: %s", result)
        result = self._do_cmd_resp(Command.GETHD, timeout=sbe16plus_driver.TIMEOUT, expected_prompt=sbe16plus_driver.Prompt.EXECUTED)
        log.debug("_handler_autosample_acquire_status: GetHD Response: %s", result)
        result = self._do_cmd_resp(Command.GETCD, timeout=sbe16plus_driver.TIMEOUT, expected_prompt=sbe16plus_driver.Prompt.EXECUTED)
        log.debug("_handler_autosample_acquire_status: GetCD Response: %s", result)
        result = self._do_cmd_resp(Command.GETCC, timeout=sbe16plus_driver.TIMEOUT, expected_prompt=sbe16plus_driver.Prompt.EXECUTED)
        log.debug("_handler_autosample_acquire_status: GetCC Response: %s", result)

        log.debug("_handler_autosample_acquire_status: sending the QS command to restart sampling")
        self._protocol_fsm.on_event(sbe16plus_driver.ProtocolEvent.QUIT_SESSION)

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
        prompt = self._wakeup(timeout=sbe16plus_driver.WAKEUP_TIMEOUT, delay=0.3)
        prompt = self._wakeup(timeout=sbe16plus_driver.WAKEUP_TIMEOUT, delay=0.3)

        kwargs['timeout'] = sbe16plus_driver.TIMEOUT
        result = self._do_cmd_resp(Command.GETCC, expected_prompt=sbe16plus_driver.Prompt.EXECUTED, *args, **kwargs)
        log.debug("_handler_autosample_get_configuration: GetCC Response: %s", result)

        log.debug("_handler_autosample_get_configuration: sending the QS command to restart sampling")
        self._protocol_fsm.on_event(sbe16plus_driver.ProtocolEvent.QUIT_SESSION)

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

        if prompt not in [sbe16plus_driver.Prompt.COMMAND, sbe16plus_driver.Prompt.EXECUTED]: 
            log.error('_validate_GetSD_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetSD command - correct instrument prompt missing: %s.' % response)
        
        if not SBE16StatusDataParticle.regex_compiled().search(response):
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

        if prompt not in [sbe16plus_driver.Prompt.COMMAND, sbe16plus_driver.Prompt.EXECUTED]: 
            log.error('_validate_GetHD_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetHD command - correct instrument prompt missing: %s.' % response)
        
        if not SBE16HardwareDataParticle.regex_compiled().search(response):
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

        if prompt not in [sbe16plus_driver.Prompt.COMMAND, sbe16plus_driver.Prompt.EXECUTED]: 
            log.error('_validate_GetCD_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetCD command - correct instrument prompt missing: %s.' % response)
        
        if not SBE16ConfigurationDataParticle.regex_compiled().search(response):
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

        if prompt not in [sbe16plus_driver.Prompt.COMMAND, sbe16plus_driver.Prompt.EXECUTED]: 
            log.error('_validate_GetCC_response: correct instrument prompt missing: %s.' % response)
            raise InstrumentProtocolException('GetCC command - correct instrument prompt missing: %s.' % response)
        
        if not SBE16CalibrationDataParticle.regex_compiled().search(response):
            log.error('_validate_GetCC_response: GetCC command not recognized: %s.' % response)
            raise InstrumentProtocolException('GetCC command not recognized: %s.' % response)
            
        return response

    ########################################################################
    # Private helpers.
    ########################################################################

    def _build_param_dict(self):
        sbe16plus_driver.SBE16Protocol._build_param_dict(self)
        
        self._param_dict.add(sbe16plus_driver.Parameter.VOLT2,
                             r'Ext Volt 2 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 2",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(sbe16plus_driver.Parameter.VOLT3,
                             r'Ext Volt 3 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 3",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(sbe16plus_driver.Parameter.VOLT4,
                             r'Ext Volt 4 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 4",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(sbe16plus_driver.Parameter.VOLT5,
                             r'Ext Volt 5 = ([\w]+)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Volt 5",
                             startup_param = True,
                             direct_access = True,
                             default_value = False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(sbe16plus_driver.Parameter.OPTODE,
                             r'OPTODE = (yes|no)',
                             lambda match : True if match.group(1) == 'yes' else False,
                             self._true_false_to_string,
                             type=ParameterDictType.BOOL,
                             display_name="Optode Attached",
                             startup_param = True,
                             direct_access = True,
                             default_value = True,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(sbe16plus_driver.Parameter.PTYPE,
                             r'pressure sensor = ([\w\s]+),',
                             self._pressure_sensor_to_int,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             display_name="Pressure Sensor Type",
                             startup_param = True,
                             direct_access = True,
                             default_value = 3,
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(sbe16plus_driver.Parameter.NCYCLES,
                             r'number of measurements per sample = (\d+)',
                             lambda match : int(match.group(1)),
                             str,
                             type=ParameterDictType.INT,
                             display_name="Ncycles",
                             startup_param = True,
                             direct_access = False)
        self._param_dict.add(sbe16plus_driver.Parameter.PAROS_INTEGRATION,
                             r'Paros integration time = (\d+\.\d+)',
                             lambda match : float(match.group(1)),
                             self._float_to_string,
                             type=ParameterDictType.FLOAT,
                             display_name="Paros integration time",
                             startup_param = True,
                             direct_access = True,
                             default_value = 1.0,
                             visibility=ParameterDictVisibility.IMMUTABLE)
