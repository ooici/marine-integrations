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

from xml.dom.minidom import parse, parseString

import re

import mi.instrument.seabird.sbe16plus_v2.driver as sbe16plus_driver

import mi.instrument.seabird.driver as seabird_driver

from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue

from mi.core.common import BaseEnum

from mi.core.exceptions import SampleException, \
                               InstrumentProtocolException

class DataParticleType(sbe16plus_driver.DataParticleType):
    DEVICE_HARDWARE = 'ctdbp_cdef_hardware'


###############################################################################
# Particles
###############################################################################

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

    def _extract_elements(self, node, tag):
        elements = node.getElementsByTagName(tag)
        if len(elements) == 0:
            raise SampleException("No %s in hardware data: [%s]" % (tag, self.raw_data))
        return elements

    def _extract_element_value(self, node, tag):
        elements = self._extract_elements(node, tag)
        children = elements[0].childNodes
        if len(children) == 0:
            raise SampleException("No value for %s in hardware data: [%s]" % (tag, self.raw_data))
        return children[0].nodeValue
    
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
        serial_number = root.getAttribute(SERIAL_NUMBER)
        
        firmware_version = self._extract_element_value(root, FIRMWARE_VERSION)
        firmware_date = self._extract_element_value(root, FIRMWARE_DATE)
        command_set_version = self._extract_element_value(root, COMMAND_SET_VERSION)
        manufacture_date = self._extract_element_value(root, MANUFATURE_DATE)
        
        pcb_assembly_elements = self._extract_elements(root, PCB_ASSEMBLY)
        pcb_serial_number = []
        pcb_assembly = []
        for assembly in pcb_assembly_elements:
            pcb_serial_number.append(assembly.getAttribute(PCB_SERIAL_NUMBER))
            pcb_assembly.append(assembly.getAttribute(ASSEMBLY_NUMBER))
        
        internal_sensors_element = self._extract_elements(root, INTERNAL_SENSORS)[0]
        sensors = self._extract_elements(internal_sensors_element, SENSOR)
        for sensor in sensors:
            sensor_id = sensor.getAttribute(ID)
            if sensor_id == TEMPERATURE_SENSOR_ID:
                temperature_sensor_serial_number = self._extract_element_value(sensor, SERIAL_NUMBER)
            elif sensor_id == CONDUCTIVITY_SENSOR_ID:
                conductivity_sensor_serial_number = self._extract_element_value(sensor, SERIAL_NUMBER)
            elif sensor_id == PRESSURE_SENSOR_ID:
                pressure_sensor_serial_number = self._extract_element_value(sensor, SERIAL_NUMBER)
                pressure_sensor_type = self._extract_element_value(sensor, TYPE)                

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


###############################################################################
# Seabird Electronics 16plus V2 NO Driver.
###############################################################################

class SBE16_NO_InstrumentDriver(sbe16plus_driver.SBE16InstrumentDriver):
    
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
    
    @staticmethod
    def sieve_function(raw_data):
        """ The method that splits samples
        Over-ride sieve function to handle additional particles.
        """
        matchers = []
        return_list = []

        """
        matchers.append(SBE16DataParticle.regex_compiled())
        matchers.append(SBE16StatusParticle.regex_compiled())
        matchers.append(SBE16CalibrationParticle.regex_compiled())
        """
        matchers.append(SBE16HardwareDataParticle.regex_compiled())

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
        if not (self._extract_sample(SBE16HardwareDataParticle, SBE16HardwareDataParticle.regex_compiled(), chunk, timestamp)):
            raise InstrumentProtocolException("Unhandled chunk %s" %chunk)

