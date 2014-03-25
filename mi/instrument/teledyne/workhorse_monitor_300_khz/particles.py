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
from mi.instrument.teledyne.particles import ADCP_SYSTEM_CONFIGURATION_KEY


from mi.core.exceptions import SampleException

#
# Particle Regex's'
#



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


class ADCP_COMPASS_CALIBRATION_KEY(BaseEnum):
    # from AC command / CALIBRATION_RAW_DATA
    FLUXGATE_CALIBRATION_TIMESTAMP = "fluxgate_calibration_timestamp"
    S_INVERSE_BX = "s_inverse_bx"
    S_INVERSE_BY = "s_inverse_by"
    S_INVERSE_BZ = "s_inverse_bz"
    S_INVERSE_ERR = "s_inverse_err"
    COIL_OFFSET = "coil_offset"
    ELECTRICAL_NULL = "electrical_null"
    TILT_CALIBRATION_TIMESTAMP = "tilt_calibration_timestamp"
    CALIBRATION_TEMP = "calibration_temp"
    ROLL_UP_DOWN = "roll_up_down"
    PITCH_UP_DOWN = "pitch_up_down"
    OFFSET_UP_DOWN = "offset_up_down"
    TILT_NULL = "tilt_null"

