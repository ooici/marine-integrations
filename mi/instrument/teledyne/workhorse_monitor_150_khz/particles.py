"""
@package mi.instrument.teledyne.workhorse_monitor_75_khz.particles
@file marine-integrations/mi/instrument/teledyne/workhorse_monitor_75_khz/driver.py
@author Roger Unwin
@brief Driver particle code for the teledyne 75_khz particles
Release notes:
"""

import re
from struct import *
import time as time
import datetime as dt

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.instrument.teledyne.driver import NEWLINE
from mi.instrument.teledyne.driver import TIMEOUT

from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType

from mi.instrument.teledyne.particles import DataParticleType

from mi.core.exceptions import SampleException

#
# Particle Regex's'
#

ADCP_PD0_PARSED_REGEX = r'\x7f\x7f(..)' # .*
ADCP_PD0_PARSED_REGEX_MATCHER = re.compile(ADCP_PD0_PARSED_REGEX, re.DOTALL)

ADCP_SYSTEM_CONFIGURATION_REGEX = r'(Instrument S/N.*?)\>'
ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER = re.compile(ADCP_SYSTEM_CONFIGURATION_REGEX, re.DOTALL)

ADCP_COMPASS_CALIBRATION_REGEX = r'(ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM.*?)\>'
ADCP_COMPASS_CALIBRATION_REGEX_MATCHER = re.compile(ADCP_COMPASS_CALIBRATION_REGEX, re.DOTALL)


class ADCP_SYSTEM_CONFIGURATION_KEY(BaseEnum):
    # https://confluence.oceanobservatories.org/display/instruments/ADCP+Driver
    # from PS0
    SERIAL_NUMBER = "serial_number"
    TRANSDUCER_FREQUENCY = "transducer_frequency"
    CONFIGURATION = "configuration"
    MATCH_LAYER = "match_layer"
    BEAM_ANGLE = "beam_angle"
    BEAM_PATTERN = "beam_pattern"
    ORIENTATION = "orientation"
    SENSORS = "sensors"
    #PRESSURE_COEFF_c3 = "pressure_coeff_c3"
    #PRESSURE_COEFF_c2 = "pressure_coeff_c2"
    #PRESSURE_COEFF_c1 = "pressure_coeff_c1"
    #PRESSURE_COEFF_OFFSET = "pressure_coeff_offset"
    TEMPERATURE_SENSOR_OFFSET = "temperature_sensor_offset"
    CPU_FIRMWARE = "cpu_firmware"
    BOOT_CODE_REQUIRED = "boot_code_required"
    BOOT_CODE_ACTUAL = "boot_code_actual"
    DEMOD_1_VERSION = "demod_1_version"
    DEMOD_1_TYPE = "demod_1_type"
    DEMOD_2_VERSION = "demod_2_version"
    DEMOD_2_TYPE = "demod_2_type"
    POWER_TIMING_VERSION = "power_timing_version"
    POWER_TIMING_TYPE = "power_timing_type"
    BOARD_SERIAL_NUMBERS = "board_serial_numbers"


class ADCP_SYSTEM_CONFIGURATION_DataParticle(DataParticle):
    _data_particle_type = DataParticleType.ADCP_SYSTEM_CONFIGURATION

    RE00 = re.compile(r'Instrument S/N: +(\d+)')
    RE01 = re.compile(r'       Frequency: +(\d+) HZ')
    RE02 = re.compile(r'   Configuration: +([a-zA-Z0-9, ]+)')
    RE03 = re.compile(r'     Match Layer: +(\d+)')
    RE04 = re.compile(r'      Beam Angle:  ([0-9.]+) DEGREES')
    RE05 = re.compile(r'    Beam Pattern:  ([a-zA-Z]+)')
    RE06 = re.compile(r'     Orientation:  ([a-zA-Z]+)')
    RE07 = re.compile(r'       Sensor\(s\):  ([a-zA-Z0-9 ]+)')

    RE14 = re.compile(r'Temp Sens Offset: +([\+\-0-9.]+) degrees C')

    RE16 = re.compile(r'    CPU Firmware:  ([0-9.\[\] ]+)')
    RE17 = re.compile(r'   Boot Code Ver:  Required: +([0-9.]+) +Actual: +([0-9.]+)')
    RE18 = re.compile(r'    DEMOD #1 Ver: +([a-zA-Z0-9]+), Type: +([a-zA-Z0-9]+)')
    RE19 = re.compile(r'    DEMOD #2 Ver: +([a-zA-Z0-9]+), Type: +([a-zA-Z0-9]+)')
    RE20 = re.compile(r'    PWRTIMG  Ver: +([a-zA-Z0-9]+), Type: +([a-zA-Z0-9]+)')

    RE23 = re.compile(r' +([0-9a-zA-Z\- ]+)')
    RE24 = re.compile(r' +([0-9a-zA-Z\- ]+)')
    RE25 = re.compile(r' +([0-9a-zA-Z\- ]+)')
    RE26 = re.compile(r' +([0-9a-zA-Z\- ]+)')

    def _build_parsed_values(self):
        # Initialize
        
        matches = {}

        try:
            lines = self.raw_data.split(NEWLINE)
    
            match = self.RE00.match(lines[0])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.SERIAL_NUMBER] = match.group(1)
            match = self.RE01.match(lines[1])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.TRANSDUCER_FREQUENCY] = int(match.group(1))
            match = self.RE02.match(lines[2])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.CONFIGURATION] = match.group(1)
            match = self.RE03.match(lines[3])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.MATCH_LAYER] = match.group(1)
            match = self.RE04.match(lines[4])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_ANGLE] = int(match.group(1))
            match = self.RE05.match(lines[5])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_PATTERN] = match.group(1)
            match = self.RE06.match(lines[6])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.ORIENTATION] = match.group(1)
            match = self.RE07.match(lines[7])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.SENSORS] = match.group(1)
            match = self.RE14.match(lines[8])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.TEMPERATURE_SENSOR_OFFSET] = float(match.group(1))
            match = self.RE16.match(lines[10])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.CPU_FIRMWARE] = match.group(1)
            match = self.RE17.match(lines[11])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_REQUIRED] = match.group(1)
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_ACTUAL] = match.group(2)
            match = self.RE18.match(lines[12])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_VERSION] = match.group(1)
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_TYPE] = match.group(2)
            match = self.RE19.match(lines[13])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_VERSION] = match.group(1)
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_TYPE] = match.group(2)
            match = self.RE20.match(lines[14])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_VERSION] = match.group(1)
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_TYPE] = match.group(2)
    
            match = self.RE23.match(lines[17])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] = str(match.group(1)) + "\n"
            match = self.RE24.match(lines[18])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] += str(match.group(1)) + "\n"
            match = self.RE25.match(lines[19])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] += str(match.group(1)) + "\n"
            match = self.RE26.match(lines[20])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] += str(match.group(1)) 
        except Exception as e:
            log.error("EXCEPTION WAS !!!! " + str(e))
        result = []
        for (key, value) in matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})
        return result

class BROKE_ADCP_SYSTEM_CONFIGURATION_DataParticle(DataParticle):
    _data_particle_type = DataParticleType.ADCP_SYSTEM_CONFIGURATION

    RE00 = re.compile(r'Instrument S/N: +(\d+)')
    RE01 = re.compile(r'       Frequency: +(\d+) HZ')
    RE02 = re.compile(r'   Configuration: +([a-zA-Z0-9, ]+)')
    RE03 = re.compile(r'     Match Layer: +(\d+)')
    RE04 = re.compile(r'      Beam Angle:  ([0-9.]+) DEGREES')
    RE05 = re.compile(r'    Beam Pattern:  ([a-zA-Z]+)')
    RE06 = re.compile(r'     Orientation:  ([a-zA-Z]+)')
    RE07 = re.compile(r'       Sensor\(s\):  ([a-zA-Z0-9 ]+)')
    
    RE09 = re.compile(r'              c3 = ([\+\-0-9.E]+)')
    RE10 = re.compile(r'              c2 = ([\+\-0-9.E]+)')
    RE11 = re.compile(r'              c1 = ([\+\-0-9.E]+)')
    RE12 = re.compile(r'          Offset = ([\+\-0-9.E]+)')
    RE14 = re.compile(r'Temp Sens Offset: +([\+\-0-9.]+) degrees C')

    RE16 = re.compile(r'    CPU Firmware:  ([0-9.\[\] ]+)')
    RE17 = re.compile(r' +Boot Code Ver: +Required: +([0-9.]+) +Actual: +([0-9.]+)')
    RE18 = re.compile(r'    DEMOD #1 Ver: +([a-zA-Z0-9]+), Type: +([a-zA-Z0-9]+)')
    RE19 = re.compile(r'    DEMOD #2 Ver: +([a-zA-Z0-9]+), Type: +([a-zA-Z0-9]+)')
    RE20 = re.compile(r'    PWRTIMG  Ver: +([a-zA-Z0-9]+), Type: +([a-zA-Z0-9]+)')

    RE23 = re.compile(r' +([0-9a-zA-Z\- ]+)')
    RE24 = re.compile(r' +([0-9a-zA-Z\- ]+)')
    RE25 = re.compile(r' +([0-9a-zA-Z\- ]+)')
    RE26 = re.compile(r' +([0-9a-zA-Z\- ]+)')

    def _build_parsed_values(self):
        # Initialize
        log.error("in ADCP_SYSTEM_CONFIGURATION_DataParticle _build_parsed_values")
        matches = {}

        try:
            lines = self.raw_data.split(NEWLINE)
            line_num = 0
            log.error("LINE = " + repr(lines[0]))
        
            match = self.RE00.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.SERIAL_NUMBER] = match.group(1)

            line_num += 1
            
            match = self.RE01.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.TRANSDUCER_FREQUENCY] = int(match.group(1))

            line_num += 1
            match = self.RE02.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.CONFIGURATION] = match.group(1)
            line_num += 1
            match = self.RE03.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.MATCH_LAYER] = match.group(1)
            line_num += 1
            match = self.RE04.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_ANGLE] = int(match.group(1))
            line_num += 1
            match = self.RE05.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_PATTERN] = match.group(1)
            line_num += 1
            match = self.RE06.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.ORIENTATION] = match.group(1)
            line_num += 1
            match = self.RE07.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.SENSORS] = match.group(1)

            line_num += 1
            match = self.RE09.match(lines[line_num])
            matches[ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c3] = float(match.group(1))
            line_num += 1
            match = self.RE10.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c2] = float(match.group(1))
            line_num += 1
            match = self.RE11.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c1] = float(match.group(1))
            line_num += 1
            match = self.RE12.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_OFFSET] = float(match.group(1))
            line_num += 2
            match = self.RE14.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.TEMPERATURE_SENSOR_OFFSET] = float(match.group(1))
            line_num += 2
            match = self.RE16.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.CPU_FIRMWARE] = match.group(1)
            line_num += 1
            match = self.RE17.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_REQUIRED] = match.group(1)
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_ACTUAL] = match.group(2)
            else:
                log.error(line_num)
                log.error(lines[line_num])
                log.error(match.group(1))
                log.error(match.group(1))
                
            line_num += 1
            match = self.RE18.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_VERSION] = match.group(1)
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_TYPE] = match.group(2)
            line_num += 1
            match = self.RE19.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_VERSION] = match.group(1)
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_TYPE] = match.group(2)
            line_num += 1
            match = self.RE20.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_VERSION] = match.group(1)
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_TYPE] = match.group(2)
            line_num += 3
    
            match = self.RE23.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] = str(match.group(1)) + "\n"
            line_num += 1
            match = self.RE24.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] += str(match.group(1)) + "\n"
            line_num += 1
            match = self.RE25.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] += str(match.group(1)) + "\n"
            line_num += 1
            match = self.RE26.match(lines[line_num])
            if match:
                matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] += str(match.group(1)) + "\n"
        except Exception as e:
            log.error("GOT AN EXCEPTION" + str(e))
    
            result = []
            for (key, value) in matches.iteritems():
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: value})
    
            log.error("RETURNING result = " + repr(result))

        return result
