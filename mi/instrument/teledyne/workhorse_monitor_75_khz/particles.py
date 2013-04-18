"""
@package mi.instrument.teledyne.workhorse_monitor_75_khz.particles
@file marine-integrations/mi/instrument/teledyne/workhorse_monitor_75_khz/cgsn/driver.py
@author Lytle Johnson
@brief Driver for the cgsn
Release notes:

moving to teledyne
"""

# TODO: This file is probably temporary, move it back to driver after
#       Driver is complete.


import re
from struct import *
import time as time
import datetime as dt

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum

from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType


from mi.core.exceptions import SampleException

# newline.
NEWLINE = '\r\n'
# default timeout.
TIMEOUT = 10
#
# Particle Regex's'
#

ADCP_PD0_PARSED_REGEX = r'\x7f\x7f(..)' # .*
ADCP_PD0_PARSED_REGEX_MATCHER = re.compile(ADCP_PD0_PARSED_REGEX, re.DOTALL)

ADCP_SYSTEM_CONFIGURATION_REGEX = r'(Instrument S/N.*?)\>'
ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER = re.compile(ADCP_SYSTEM_CONFIGURATION_REGEX, re.DOTALL)

ADCP_COMPASS_CALIBRATION_REGEX = r'(ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM.*?)\>'
ADCP_COMPASS_CALIBRATION_REGEX_MATCHER = re.compile(ADCP_COMPASS_CALIBRATION_REGEX, re.DOTALL)



###############################################################################
# Data Particles
###############################################################################
class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    ADCP_PD0_PARSED = 'adcp_pd0_parsed'
    ADCP_SYSTEM_CONFIGURATION = 'adcp_system_configuration'
    ADCP_COMPASS_CALIBRATION = 'adcp_compass_calibration'

    # ENGINEERING_PARAMETERS - NONE found.


class ADCP_PD0_PARSED_KEY(BaseEnum):
    HEADER_ID = "header_id"
    DATA_SOURCE_ID = "data_source_id"
    NUM_BYTES = "num_bytes"
    NUM_DATA_TYPES = "num_data_types"
    OFFSET_DATA_TYPES = "offset_data_types"
    FIXED_LEADER_ID = "fixed_leader_id"
    FIRMWARE_VERSION = "firmware_version"
    FIRMWARE_REVISION = "firmware_revision"
    SYSCONFIG_FREQUENCY = "sysconfig_frequency"
    SYSCONFIG_BEAM_PATTERN = "sysconfig_beam_pattern"
    SYSCONFIG_SENSOR_CONFIG = "sysconfig_sensor_config"
    SYSCONFIG_HEAD_ATTACHED = "sysconfig_head_attached"
    SYSCONFIG_VERTICAL_ORIENTATION = "sysconfig_vertical_orientation"
    DATA_FLAG = "data_flag"
    LAG_LENGTH = "lag_length"
    NUM_BEAMS = "num_beams"
    NUM_CELLS = "num_cells"
    PINGS_PER_ENSEMBLE = "pings_per_ensemble"
    DEPTH_CELL_LENGTH = "depth_cell_length"
    BLANK_AFTER_TRANSMIT = "blank_after_transmit"
    SIGNAL_PROCESSING_MODE = "signal_processing_mode"
    LOW_CORR_THRESHOLD = "low_corr_threshold"
    NUM_CODE_REPETITIONS = "num_code_repetitions"
    PERCENT_GOOD_MIN = "percent_good_min"
    ERROR_VEL_THRESHOLD = "error_vel_threshold"
    TIME_PER_PING_MINUTES = "time_per_ping_minutes"
    TIME_PER_PING_SECONDS = "time_per_ping_seconds"
    COORD_TRANSFORM_TYPE = "coord_transform_type"
    COORD_TRANSFORM_TILTS = "coord_transform_tilts"
    COORD_TRANSFORM_BEAMS = "coord_transform_beams"
    COORD_TRANSFORM_MAPPING = "coord_transform_mapping"
    HEADING_ALIGNMENT = "heading_alignment"
    HEADING_BIAS = "heading_bias"

    SENSOR_SOURCE_SPEED = "sensor_source_speed"
    SENSOR_SOURCE_DEPTH = "sensor_source_depth"
    SENSOR_SOURCE_HEADING = "sensor_source_heading"
    SENSOR_SOURCE_PITCH = "sensor_source_pitch"
    SENSOR_SOURCE_ROLL = "sensor_source_roll"
    SENSOR_SOURCE_CONDUCTIVITY = "sensor_source_conductivity"
    SENSOR_SOURCE_TEMPERATURE = "sensor_source_temperature"
    SENSOR_AVAILABLE_DEPTH = "sensor_available_depth"
    SENSOR_AVAILABLE_HEADING = "sensor_available_heading"
    SENSOR_AVAILABLE_PITCH = "sensor_available_pitch"
    SENSOR_AVAILABLE_ROLL = "sensor_available_roll"
    SENSOR_AVAILABLE_CONDUCTIVITY = "sensor_available_conductivity"
    SENSOR_AVAILABLE_TEMPERATURE = "sensor_available_temperature"

    BIN_1_DISTANCE = "bin_1_distance"
    TRANSMIT_PULSE_LENGTH = "transmit_pulse_length"
    REFERENCE_LAYER_START = "reference_layer_start"
    REFERENCE_LAYER_STOP = "reference_layer_stop"
    FALSE_TARGET_THRESHOLD = "false_target_threshold"
    LOW_LATENCY_TRIGGER = "low_latency_trigger"
    TRANSMIT_LAG_DISTANCE = "transmit_lag_distance"
    CPU_BOARD_SERIAL_NUMBER = "cpu_board_serial_number"
    SYSTEM_BANDWIDTH = "system_bandwidth"
    SYSTEM_POWER = "system_power"
    SERIAL_NUMBER = "serial_number"
    BEAM_ANGLE = "beam_angle"
    VARIABLE_LEADER_ID = "variable_leader_id"
    ENSEMBLE_NUMBER = "ensemble_number"
    INTERNAL_TIMESTAMP = "internal_timestamp"
    ENSEMBLE_NUMBER_INCREMENT = "ensemble_number_increment"
    BIT_RESULT_DEMOD_1 = "bit_result_demod_1"
    BIT_RESULT_DEMOD_2 = "bit_result_demod_2"
    BIT_RESULT_TIMING = "bit_result_timing"
    SPEED_OF_SOUND = "speed_of_sound"
    TRANSDUCER_DEPTH = "transducer_depth"
    HEADING = "heading"
    PITCH = "pitch"
    ROLL = "roll"
    SALINITY = "salinity"
    TEMPERATURE = "temperature"
    MPT_MINUTES = "mpt_minutes"
    MPT_SECONDS = "mpt_seconds"
    HEADING_STDEV = "heading_stdev"
    PITCH_STDEV = "pitch_stdev"
    ROLL_STDEV = "roll_stdev"
    ADC_TRANSMIT_CURRENT = "adc_transmit_current"
    ADC_TRANSMIT_VOLTAGE = "adc_transmit_voltage"
    ADC_AMBIENT_TEMP = "adc_ambient_temp"
    ADC_PRESSURE_PLUS = "adc_pressure_plus"
    ADC_PRESSURE_MINUS = "adc_pressure_minus"
    ADC_ATTITUDE_TEMP = "adc_attitude_temp"
    ADC_ATTITUDE = "adc_attitiude"
    ADC_CONTAMINATION_SENSOR = "adc_contamination_sensor"
    BUS_ERROR_EXCEPTION = "bus_error_exception"
    ADDRESS_ERROR_EXCEPTION = "address_error_exception"
    ILLEGAL_INSTRUCTION_EXCEPTION = "illegal_instruction_exception"
    ZERO_DIVIDE_INSTRUCTION = "zero_divide_instruction"
    EMULATOR_EXCEPTION = "emulator_exception"
    UNASSIGNED_EXCEPTION = "unassigned_exception"
    WATCHDOG_RESTART_OCCURED = "watchdog_restart_occurred"
    BATTERY_SAVER_POWER = "battery_saver_power"
    PINGING = "pinging"
    COLD_WAKEUP_OCCURED = "cold_wakeup_occurred"
    UNKNOWN_WAKEUP_OCCURED = "unknown_wakeup_occurred"
    CLOCK_READ_ERROR = "clock_read_error"
    UNEXPECTED_ALARM = "unexpected_alarm"
    CLOCK_JUMP_FORWARD = "clock_jump_forward"
    CLOCK_JUMP_BACKWARD = "clock_jump_backward"
    POWER_FAIL = "power_fail"
    SPURIOUS_DSP_INTERRUPT = "spurious_dsp_interrupt"
    SPURIOUS_UART_INTERRUPT = "spurious_uart_interrupt"
    SPURIOUS_CLOCK_INTERRUPT = "spurious_clock_interrupt"
    LEVEL_7_INTERRUPT = "level_7_interrupt"
    ABSOLUTE_PRESSURE = "pressure"
    PRESSURE_VARIANCE = "pressure_variance"
    INTERNAL_TIMESTAMP = "internal_timestamp"
    VELOCITY_DATA_ID = "velocity_data_id"
    BEAM_1_VELOCITY = "beam_1_velocity" # These may live in OOICORE driver as a extension
    BEAM_2_VELOCITY = "beam_2_velocity" # These may live in OOICORE driver as a extension
    BEAM_3_VELOCITY = "beam_3_velocity" # These may live in OOICORE driver as a extension
    BEAM_4_VELOCITY = "beam_4_velocity" # These may live in OOICORE driver as a extension
    WATER_VELOCITY_EAST = "water_velocity_east" # These may live in OOICORE driver as a extension
    WATER_VELOCITY_NORTH = "water_velocity_north" # These may live in OOICORE driver as a extension
    WATER_VELOCITY_UP = "water_velocity_up" # These may live in OOICORE driver as a extension
    ERROR_VELOCITY = "error_velocity" # These may live in OOICORE driver as a extension
    CORRELATION_MAGNITUDE_ID = "correlation_magnitude_id"
    CORRELATION_MAGNITUDE_BEAM1 = "correlation_magnitude_beam1"
    CORRELATION_MAGNITUDE_BEAM2 = "correlation_magnitude_beam2"
    CORRELATION_MAGNITUDE_BEAM3 = "correlation_magnitude_beam3"
    CORRELATION_MAGNITUDE_BEAM4 = "correlation_magnitude_beam4"
    ECHO_INTENSITY_ID = "echo_intensity_id"
    ECHO_INTENSITY_BEAM1 = "echo_intesity_beam1"
    ECHO_INTENSITY_BEAM2 = "echo_intesity_beam2"
    ECHO_INTENSITY_BEAM3 = "echo_intesity_beam3"
    ECHO_INTENSITY_BEAM4 = "echo_intesity_beam4"
    PERCENT_GOOD_BEAM1 = "percent_good_beam1"# These may live in OOICORE driver as a extension
    PERCENT_GOOD_BEAM2 = "percent_good_beam2"# These may live in OOICORE driver as a extension
    PERCENT_GOOD_BEAM3 = "percent_good_beam3"# These may live in OOICORE driver as a extension
    PERCENT_GOOD_BEAM4 = "percent_good_beam4"# These may live in OOICORE driver as a extension
    PERCENT_GOOD_ID = "percent_good_id"
    PERCENT_GOOD_3BEAM = "percent_good_3beam"
    PERCENT_TRANSFORMS_REJECT = "percent_transforms_reject"
    PERCENT_BAD_BEAMS = "percent_bad_beams"
    PERCENT_GOOD_4BEAM = "percent_good_4beam"
    CHECKSUM = "checksum"


class ADCP_PD0_PARSED_DataParticle(DataParticle):
    _data_particle_type = DataParticleType.ADCP_PD0_PARSED



    def _build_parsed_values(self):
        """
        Parse the base portion of the particle
        """
        if "[BREAK Wakeup A]" in self.raw_data:
            raise SampleException("BREAK encountered, something is not right.")

        self.final_result = []

        length = unpack("H", self.raw_data[2:4])[0]

        data = str(self.raw_data)
        #
        # Calculate Checksum
        #
        total = int(0)
        for i in range(0, length):
            total += int(ord(data[i]))

        checksum = total & 65535    # bitwise and with 65535 or mod vs 65536

        if checksum != unpack("H", self.raw_data[length: length+2])[0]:
            log.debug("Checksum mismatch "+ str(checksum) + "!= " + str(unpack("H", self.raw_data[length: length+2])[0]))

            raise SampleException("Checksum mismatch")

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.CHECKSUM,
                                  DataParticleKey.VALUE: checksum})

        (header_id, data_source_id, num_bytes, filler, num_data_types) = \
            unpack('!BBHBB', self.raw_data[0:6])

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.HEADER_ID,
                                  DataParticleKey.VALUE: header_id})

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.DATA_SOURCE_ID,
                                  DataParticleKey.VALUE: data_source_id})

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.NUM_BYTES,
                                  DataParticleKey.VALUE: num_bytes})

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.NUM_DATA_TYPES,
                                  DataParticleKey.VALUE: num_data_types})

        offsets = []
        for offset in range(0, num_data_types):
            value = unpack('<H', self.raw_data[(2 * offset + 6):(2 * offset + 8)])[0]
            offsets.append(value)

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.OFFSET_DATA_TYPES,
                                  DataParticleKey.VALUE: offsets})
        offsets.append(length - 2)

        chunks = []
        for offset in range(0, num_data_types):
            chunks.append(self.raw_data[offsets[offset] : offsets[offset + 1] ])

            variable_leader_id = unpack('!H', chunks[offset][0:2])[0]

            if offset == 0:
                self.parse_fixed_chunk(chunks[offset])
            else:
                if 32768 == variable_leader_id:
                    self.parse_variable_chunk(chunks[offset])
                elif 1 == variable_leader_id:
                    self.parse_velocity_chunk(chunks[offset])
                elif 2 == variable_leader_id:
                    self.parse_corelation_magnitude_chunk(chunks[offset])
                elif 3 == variable_leader_id:
                    self.parse_echo_intensity_chunk(chunks[offset])
                elif 4 == variable_leader_id:
                    self.parse_percent_good_chunk(chunks[offset])
        return self.final_result

    def parse_fixed_chunk(self, chunk):
        """
        Parse the fixed portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        (fixed_leader_id, firmware_version, firmware_revision, sysconfig_frequency, data_flag, lag_length, num_beams, num_cells, pings_per_ensemble,
         depth_cell_length, blank_after_transmit, signal_processing_mode, low_corr_threshold, num_code_repetitions, percent_good_min, error_vel_threshold,
         time_per_ping_minutes, time_per_ping_seconds, time_per_ping_hundredths, coord_transform_type, heading_alignment, heading_bias, sensor_source,
         sensor_available, bin_1_distance, transmit_pulse_length, reference_layer_start, reference_layer_stop, false_target_threshold,
         low_latency_trigger, transmit_lag_distance, cpu_board_serial_number, system_bandwidth, system_power,
         spare, serial_number, beam_angle) \
        = unpack('!HBBHbBBBHHHBBBBHBBBBhhBBHHBBBBHQHBBIB', chunk[0:59])

        if 0 != fixed_leader_id:
            raise SampleException("fixed_leader_id was not equal to 0")

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.FIXED_LEADER_ID,
                                  DataParticleKey.VALUE: fixed_leader_id})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.FIRMWARE_VERSION,
                                  DataParticleKey.VALUE: firmware_version})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.FIRMWARE_REVISION,
                                  DataParticleKey.VALUE: firmware_revision})

        frequencies = [75, 150, 300, 600, 1200, 2400]

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SYSCONFIG_FREQUENCY,
                                  DataParticleKey.VALUE: frequencies[sysconfig_frequency & 0b00000111]})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SYSCONFIG_BEAM_PATTERN,
                                  DataParticleKey.VALUE: 1 if sysconfig_frequency & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SYSCONFIG_SENSOR_CONFIG,
                                  DataParticleKey.VALUE: sysconfig_frequency & 0b00110000 >> 4})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SYSCONFIG_HEAD_ATTACHED,
                                  DataParticleKey.VALUE: 1 if sysconfig_frequency & 0b01000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SYSCONFIG_VERTICAL_ORIENTATION,
                                  DataParticleKey.VALUE: 1 if sysconfig_frequency & 0b10000000 else 0})

        if 0 != data_flag:
            raise SampleException("data_flag was not equal to 0")

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.DATA_FLAG,
                                  DataParticleKey.VALUE: data_flag})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.LAG_LENGTH,
                                  DataParticleKey.VALUE: lag_length})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.NUM_BEAMS,
                                  DataParticleKey.VALUE: num_beams})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.NUM_CELLS,
                                  DataParticleKey.VALUE: num_cells})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PINGS_PER_ENSEMBLE,
                                  DataParticleKey.VALUE: pings_per_ensemble})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.DEPTH_CELL_LENGTH,
                                  DataParticleKey.VALUE: depth_cell_length})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BLANK_AFTER_TRANSMIT,
                                  DataParticleKey.VALUE: blank_after_transmit})

        if 1 != signal_processing_mode:
            raise SampleException("signal_processing_mode was not equal to 1")

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SIGNAL_PROCESSING_MODE,
                                  DataParticleKey.VALUE: signal_processing_mode})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.LOW_CORR_THRESHOLD,
                                  DataParticleKey.VALUE: low_corr_threshold})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.NUM_CODE_REPETITIONS,
                                  DataParticleKey.VALUE: num_code_repetitions})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_MIN,
                                  DataParticleKey.VALUE: percent_good_min})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ERROR_VEL_THRESHOLD,
                                  DataParticleKey.VALUE: error_vel_threshold})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.TIME_PER_PING_MINUTES,
                                  DataParticleKey.VALUE: time_per_ping_minutes})

        tpp_float_seconds = float(time_per_ping_seconds + (time_per_ping_hundredths/100))
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.TIME_PER_PING_SECONDS,
                                  DataParticleKey.VALUE: tpp_float_seconds})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.COORD_TRANSFORM_TYPE,
                                  DataParticleKey.VALUE: coord_transform_type & 0b00011000 >> 3})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.COORD_TRANSFORM_TILTS,
                                  DataParticleKey.VALUE: 1 if coord_transform_type & 0b00000100 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.COORD_TRANSFORM_BEAMS,
                                  DataParticleKey.VALUE: 1 if coord_transform_type & 0b0000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.COORD_TRANSFORM_MAPPING,
                                  DataParticleKey.VALUE: 1 if coord_transform_type & 0b00000001 else 0})

        # lame, but expedient - mask off un-needed bits
        self.coord_transform_type = coord_transform_type & 0b00011000  

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.HEADING_ALIGNMENT,
                                  DataParticleKey.VALUE: heading_alignment})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.HEADING_BIAS,
                                  DataParticleKey.VALUE: heading_bias})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_SPEED,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b01000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_DEPTH,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b00100000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_HEADING,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b00010000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_PITCH,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_ROLL,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b00000100 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_CONDUCTIVITY,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b00000010 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_TEMPERATURE,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b00000001 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_DEPTH,
                                  DataParticleKey.VALUE: 1 if sensor_available & 0b00100000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_HEADING,
                                  DataParticleKey.VALUE: 1 if sensor_available & 0b00010000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_PITCH,
                                  DataParticleKey.VALUE: 1 if sensor_available & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_ROLL,
                                  DataParticleKey.VALUE: 1 if sensor_available & 0b00000100 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_CONDUCTIVITY,
                                  DataParticleKey.VALUE: 1 if sensor_available & 0b00000010 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_TEMPERATURE,
                                  DataParticleKey.VALUE: 1 if sensor_available & 0b00000001 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BIN_1_DISTANCE,
                                  DataParticleKey.VALUE: bin_1_distance})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.TRANSMIT_PULSE_LENGTH,
                                  DataParticleKey.VALUE: transmit_pulse_length})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.REFERENCE_LAYER_START,
                                  DataParticleKey.VALUE: reference_layer_start})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.REFERENCE_LAYER_STOP,
                                  DataParticleKey.VALUE: reference_layer_stop})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.FALSE_TARGET_THRESHOLD,
                                  DataParticleKey.VALUE: false_target_threshold})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.LOW_LATENCY_TRIGGER,
                                  DataParticleKey.VALUE: low_latency_trigger})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.TRANSMIT_LAG_DISTANCE,
                                  DataParticleKey.VALUE: transmit_lag_distance})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.CPU_BOARD_SERIAL_NUMBER,
                                  DataParticleKey.VALUE: cpu_board_serial_number})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SYSTEM_BANDWIDTH,
                                  DataParticleKey.VALUE: system_bandwidth})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SYSTEM_POWER,
                                  DataParticleKey.VALUE: system_power})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SERIAL_NUMBER,
                                  DataParticleKey.VALUE: serial_number})     
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BEAM_ANGLE,
                                  DataParticleKey.VALUE: beam_angle})

    def parse_variable_chunk(self, chunk):
        """
        Parse the variable portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        rtc = {}
        rtc2k = {}
        (variable_leader_id, ensemble_number,
         rtc['year'], rtc['month'], rtc['day'], rtc['hour'], rtc['minute'], rtc['second'], rtc['hundredths'],
         ensemble_number_increment,
         error_bit_field, reserved_error_bit_field, speed_of_sound, transducer_depth,
         heading, pitch, roll, salinity, temperature,
         mpt_minutes, mpt_seconds_component, mpt_hundredths_component,
         heading_stdev, pitch_stdev, roll_stdev,
         adc_transmit_current, adc_transmit_voltage, adc_ambient_temp, adc_pressure_plus,
         adc_pressure_minus, adc_attitude_temp, adc_attitiude, adc_contamination_sensor,
         error_status_word_1, error_status_word_2, error_status_word_3, error_status_word_4,
         RESERVED1, RESERVED2, pressure, RESERVED3, pressure_variance,
         rtc2k['century'], rtc2k['year'], rtc2k['month'], rtc2k['day'], rtc2k['hour'], rtc2k['minute'], rtc2k['second'], rtc2k['hundredths']) \
        = unpack('<HHBBBBBBBBBBHHHhhHhBBBBBBBBBBBBBBBBBBBBLBLBBBBBBBB', chunk[0:65])

        if 128 != variable_leader_id:
            raise SampleException("variable_leader_id was not equal to 128")

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.VARIABLE_LEADER_ID,
                                  DataParticleKey.VALUE: variable_leader_id})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ENSEMBLE_NUMBER,
                                  DataParticleKey.VALUE: ensemble_number})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ENSEMBLE_NUMBER_INCREMENT,
                                  DataParticleKey.VALUE: ensemble_number_increment})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BIT_RESULT_DEMOD_1,
                                  DataParticleKey.VALUE: 1 if error_bit_field & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BIT_RESULT_DEMOD_2,
                                  DataParticleKey.VALUE: 1 if error_bit_field & 0b00010000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BIT_RESULT_TIMING,
                                  DataParticleKey.VALUE: 1 if error_bit_field & 0b00000010 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SPEED_OF_SOUND,
                                  DataParticleKey.VALUE: speed_of_sound})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.TRANSDUCER_DEPTH,
                                  DataParticleKey.VALUE: transducer_depth})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.HEADING,
                                  DataParticleKey.VALUE: heading})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PITCH,
                                  DataParticleKey.VALUE: pitch})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ROLL,
                                  DataParticleKey.VALUE: roll})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SALINITY,
                                  DataParticleKey.VALUE: salinity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.TEMPERATURE,
                                  DataParticleKey.VALUE: temperature})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.MPT_MINUTES,
                                  DataParticleKey.VALUE: mpt_minutes})

        mpt_seconds = float(mpt_seconds_component + (mpt_hundredths_component/100))
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.MPT_SECONDS,
                                  DataParticleKey.VALUE: mpt_seconds})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.HEADING_STDEV,
                                  DataParticleKey.VALUE: heading_stdev})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PITCH_STDEV,
                                  DataParticleKey.VALUE: pitch_stdev})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ROLL_STDEV,
                                  DataParticleKey.VALUE: roll_stdev})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ADC_TRANSMIT_CURRENT,
                                  DataParticleKey.VALUE: adc_transmit_current})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ADC_TRANSMIT_VOLTAGE,
                                  DataParticleKey.VALUE: adc_transmit_voltage})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ADC_AMBIENT_TEMP,
                                  DataParticleKey.VALUE: adc_ambient_temp})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ADC_PRESSURE_PLUS,
                                  DataParticleKey.VALUE: adc_pressure_plus})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ADC_PRESSURE_MINUS,
                                  DataParticleKey.VALUE: adc_pressure_minus})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ADC_ATTITUDE_TEMP,
                                  DataParticleKey.VALUE: adc_attitude_temp})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ADC_ATTITUDE,
                                  DataParticleKey.VALUE: adc_attitiude})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ADC_CONTAMINATION_SENSOR,
                                  DataParticleKey.VALUE: adc_contamination_sensor})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BUS_ERROR_EXCEPTION,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00000001 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ADDRESS_ERROR_EXCEPTION,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00000010 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ILLEGAL_INSTRUCTION_EXCEPTION,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00000100 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ZERO_DIVIDE_INSTRUCTION,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.EMULATOR_EXCEPTION,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00010000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.UNASSIGNED_EXCEPTION,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00100000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.WATCHDOG_RESTART_OCCURED,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b01000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BATTERY_SAVER_POWER,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b10000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PINGING,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00000001 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.COLD_WAKEUP_OCCURED,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b01000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.UNKNOWN_WAKEUP_OCCURED,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b10000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.CLOCK_READ_ERROR,
                                  DataParticleKey.VALUE: 1 if error_status_word_3 & 0b00000001 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.UNEXPECTED_ALARM,
                                  DataParticleKey.VALUE: 1 if error_status_word_3 & 0b00000010 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.CLOCK_JUMP_FORWARD,
                                  DataParticleKey.VALUE: 1 if error_status_word_3 & 0b00000100 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.CLOCK_JUMP_BACKWARD,
                                  DataParticleKey.VALUE: 1 if error_status_word_3 & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.POWER_FAIL,
                                  DataParticleKey.VALUE: 1 if error_status_word_4 & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SPURIOUS_DSP_INTERRUPT,
                                  DataParticleKey.VALUE: 1 if error_status_word_4 & 0b00010000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SPURIOUS_UART_INTERRUPT,
                                  DataParticleKey.VALUE: 1 if error_status_word_4 & 0b00100000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.SPURIOUS_CLOCK_INTERRUPT,
                                  DataParticleKey.VALUE: 1 if error_status_word_4 & 0b01000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.LEVEL_7_INTERRUPT,
                                  DataParticleKey.VALUE: 1 if error_status_word_4 & 0b10000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ABSOLUTE_PRESSURE,
                                  DataParticleKey.VALUE: pressure})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PRESSURE_VARIANCE,
                                  DataParticleKey.VALUE: pressure_variance})

        dts = dt.datetime(rtc2k['century'] * 100 + rtc2k['year'],
                               rtc2k['month'],
                               rtc2k['day'],
                               rtc2k['hour'],
                               rtc2k['minute'],
                               rtc2k['second'])

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.INTERNAL_TIMESTAMP,
                                 DataParticleKey.VALUE: time.mktime(dts.timetuple()) + (rtc2k['second'] / 100.0)})

    def parse_velocity_chunk(self, chunk):
        """
        Parse the velocity portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        N = (len(chunk) - 2) / 2 /4
        offset = 0

        velocity_data_id = unpack("!H", chunk[0:2])[0]
        if 1 != velocity_data_id:
            raise SampleException("velocity_data_id was not equal to 1")
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.VELOCITY_DATA_ID,
                                      DataParticleKey.VALUE: velocity_data_id})

        if 0 == self.coord_transform_type: # BEAM Coordinates
            beam_1_velocity = []
            beam_2_velocity = []
            beam_3_velocity = []
            beam_4_velocity = []
            for row in range (1, N):
                (a,b,c,d) = unpack('!HHHH', chunk[offset + 2: offset + 10])
                beam_1_velocity.append(a)
                beam_2_velocity.append(b)
                beam_3_velocity.append(c)
                beam_4_velocity.append(d)
                offset += 4 * 2
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BEAM_1_VELOCITY,
                                      DataParticleKey.VALUE: beam_1_velocity})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BEAM_2_VELOCITY,
                                      DataParticleKey.VALUE: beam_2_velocity})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BEAM_3_VELOCITY,
                                      DataParticleKey.VALUE: beam_3_velocity})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BEAM_4_VELOCITY,
                                      DataParticleKey.VALUE: beam_4_velocity})
            # place holders
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.WATER_VELOCITY_EAST,
                                      DataParticleKey.VALUE: []})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.WATER_VELOCITY_NORTH,
                                      DataParticleKey.VALUE: []})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.WATER_VELOCITY_UP,
                                      DataParticleKey.VALUE: []})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ERROR_VELOCITY,
                                      DataParticleKey.VALUE: []})

        elif 3 == self.coord_transform_type: # Earth Coordinates
            water_velocity_east = []
            water_velocity_north = []
            water_velocity_up = []
            error_velocity = []
            for row in range (1, N):
                (a,b,c,d) = unpack('!HHHH', chunk[offset + 2: offset + 10])
                water_velocity_east.append(a)
                water_velocity_north.append(b)
                water_velocity_up.append(c)
                error_velocity.append(d)
                offset += 4 * 2
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.WATER_VELOCITY_EAST,
                                      DataParticleKey.VALUE: water_velocity_east})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.WATER_VELOCITY_NORTH,
                                      DataParticleKey.VALUE: water_velocity_north})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.WATER_VELOCITY_UP,
                                      DataParticleKey.VALUE: water_velocity_up})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ERROR_VELOCITY,
                                      DataParticleKey.VALUE: error_velocity})
            # place holders
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BEAM_1_VELOCITY,
                                      DataParticleKey.VALUE: []})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BEAM_2_VELOCITY,
                                      DataParticleKey.VALUE: []})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BEAM_3_VELOCITY,
                                      DataParticleKey.VALUE: []})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.BEAM_4_VELOCITY,
                                      DataParticleKey.VALUE: []})
        else:
            raise SampleException("coord_transform_type not coded for. " + str(self.coord_transform_type))

    def parse_corelation_magnitude_chunk(self, chunk):
        """
        Parse the corelation magnitude portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        N = (len(chunk) - 2) / 2 /4
        offset = 0

        correlation_magnitude_id = unpack("!H", chunk[0:2])[0]
        if 2 != correlation_magnitude_id:
            raise SampleException("correlation_magnitude_id was not equal to 2")
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_ID,
                                      DataParticleKey.VALUE: correlation_magnitude_id})

        correlation_magnitude_beam1 = []
        correlation_magnitude_beam2 = []
        correlation_magnitude_beam3 = []
        correlation_magnitude_beam4 = []
        for row in range (1, N):
            (a, b, c, d) = unpack('!HHHH', chunk[offset + 2: offset + 10])
            correlation_magnitude_beam1.append(a)
            correlation_magnitude_beam2.append(b)
            correlation_magnitude_beam3.append(c)
            correlation_magnitude_beam4.append(d)
            offset += 4 * 2

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM1,
                                  DataParticleKey.VALUE: correlation_magnitude_beam1})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM2,
                                  DataParticleKey.VALUE: correlation_magnitude_beam2})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM3,
                                  DataParticleKey.VALUE: correlation_magnitude_beam3})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM4,
                                  DataParticleKey.VALUE: correlation_magnitude_beam4})

    def parse_echo_intensity_chunk(self, chunk):
        """
        Parse the echo intensity portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        N = (len(chunk) - 2) / 2 /4
        offset = 0

        echo_intensity_id = unpack("!H", chunk[0:2])[0]
        if 3 != echo_intensity_id:
            raise SampleException("echo_intensity_id was not equal to 3")
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_ID,
                                      DataParticleKey.VALUE: echo_intensity_id})

        echo_intesity_beam1 = []
        echo_intesity_beam2 = []
        echo_intesity_beam3 = []
        echo_intesity_beam4 = []
        for row in range (1, N):
            (a, b, c, d) = unpack('!HHHH', chunk[offset + 2: offset + 10])
            echo_intesity_beam1.append(a)
            echo_intesity_beam2.append(b)
            echo_intesity_beam3.append(c)
            echo_intesity_beam4.append(d)
            offset += 4 * 2

        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM1,
                                  DataParticleKey.VALUE: echo_intesity_beam1})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM2,
                                  DataParticleKey.VALUE: echo_intesity_beam2})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM3,
                                  DataParticleKey.VALUE: echo_intesity_beam3})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM4,
                                  DataParticleKey.VALUE: echo_intesity_beam4})

    def parse_percent_good_chunk(self, chunk):
        """
        Parse the percent good portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        N = (len(chunk) - 2) / 2 /4
        offset = 0

        # coord_transform_type
        # Coordinate Transformation type:
        #    0 = None (Beam), 1 = Instrument, 2 = Ship, 3 = Earth.

        percent_good_id = unpack("!H", chunk[0:2])[0]
        if 4 != percent_good_id:
            raise SampleException("percent_good_id was not equal to 4")
        self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_ID,
                                      DataParticleKey.VALUE: percent_good_id})

        if 0 == self.coord_transform_type: # BEAM Coordinates
            percent_good_beam1 = []
            percent_good_beam2 = []
            percent_good_beam3 = []
            percent_good_beam4 = []
            for row in range (1, N):
                (a,b,c,d) = unpack('!HHHH', chunk[offset + 2: offset + 10])
                percent_good_beam1.append(a)
                percent_good_beam2.append(b)
                percent_good_beam3.append(c)
                percent_good_beam4.append(d)
                offset += 4 * 2
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM1,
                                      DataParticleKey.VALUE: percent_good_beam1})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM2,
                                      DataParticleKey.VALUE: percent_good_beam2})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM3,
                                      DataParticleKey.VALUE: percent_good_beam3})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM4,
                                      DataParticleKey.VALUE: percent_good_beam4})
            # unused place holders
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_3BEAM,
                                      DataParticleKey.VALUE: []})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_TRANSFORMS_REJECT,
                                      DataParticleKey.VALUE: []})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_BAD_BEAMS,
                                      DataParticleKey.VALUE: []})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_4BEAM,
                                      DataParticleKey.VALUE: []})

        elif 3 == self.coord_transform_type: # Earth Coordinates
            percent_good_3beam = []
            percent_transforms_reject = []
            percent_bad_beams = []
            percent_good_4beam = []
            for row in range (1, N):
                (a,b,c,d) = unpack('!HHHH', chunk[offset + 2: offset + 10])
                percent_good_3beam.append(a)
                percent_transforms_reject.append(b)
                percent_bad_beams.append(c)
                percent_good_4beam.append(d)
                offset += 4 * 2
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_3BEAM,
                                      DataParticleKey.VALUE: percent_good_3beam})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_TRANSFORMS_REJECT,
                                      DataParticleKey.VALUE: percent_transforms_reject})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_BAD_BEAMS,
                                      DataParticleKey.VALUE: percent_bad_beams})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_4BEAM,
                                      DataParticleKey.VALUE: percent_good_4beam})
            # unused place holders
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM1,
                                      DataParticleKey.VALUE: []})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM2,
                                      DataParticleKey.VALUE: []})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM3,
                                      DataParticleKey.VALUE: []})
            self.final_result.append({DataParticleKey.VALUE_ID: ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM4,
                                      DataParticleKey.VALUE: []})
        else:
            raise SampleException("coord_transform_type not coded for." + str(self.coord_transform_type))

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
    PRESSURE_COEFF_c3 = "pressure_coeff_c3"
    PRESSURE_COEFF_c2 = "pressure_coeff_c2"
    PRESSURE_COEFF_c1 = "pressure_coeff_c1"
    PRESSURE_COEFF_OFFSET = "pressure_coeff_offset"
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

    RE09 = re.compile(r'              c3 = ([\+\-0-9.E]+)')
    RE10 = re.compile(r'              c2 = ([\+\-0-9.E]+)')
    RE11 = re.compile(r'              c1 = ([\+\-0-9.E]+)')
    RE12 = re.compile(r'          Offset = ([\+\-0-9.E]+)')

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
    RE27 = re.compile(r' +([0-9a-zA-Z\- ]+)')
    RE28 = re.compile(r' +([0-9a-zA-Z\- ]+)')

    def _build_parsed_values(self):
        """
        """
        # Initialize
        matches = {}

        lines = self.raw_data.split(NEWLINE)

        match = self.RE00.match(lines[0])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.SERIAL_NUMBER] = "18444" # match.group(1)
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
        match = self.RE09.match(lines[9])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c3] = float(match.group(1))
        match = self.RE10.match(lines[10])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c2] = float(match.group(1))
        match = self.RE11.match(lines[11])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c1] = float(match.group(1))
        match = self.RE12.match(lines[12])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_OFFSET] = float(match.group(1))
        match = self.RE14.match(lines[14])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.TEMPERATURE_SENSOR_OFFSET] = float(match.group(1))
        match = self.RE16.match(lines[16])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.CPU_FIRMWARE] = match.group(1)
        match = self.RE17.match(lines[17])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_REQUIRED] = match.group(1)
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_ACTUAL] = match.group(2)
        match = self.RE18.match(lines[18])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_VERSION] = match.group(1)
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_TYPE] = match.group(2)
        match = self.RE19.match(lines[19])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_VERSION] = match.group(1)
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_TYPE] = match.group(2)
        match = self.RE20.match(lines[20])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_VERSION] = match.group(1)
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_TYPE] = match.group(2)

        match = self.RE23.match(lines[23])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] = str(match.group(1) + "\n")
        match = self.RE24.match(lines[24])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] += str(match.group(1) + "\n")
        match = self.RE25.match(lines[25])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] += str(match.group(1) + "\n")
        match = self.RE26.match(lines[26])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] += str(match.group(1) + "\n")
        match = self.RE27.match(lines[27])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] += str(match.group(1) + "\n")
        match = self.RE28.match(lines[28])
        matches[ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS] += str(match.group(1))

        result = []
        for (key, value) in matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

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


class ADCP_COMPASS_CALIBRATION_DataParticle(DataParticle):
    _data_particle_type = DataParticleType.ADCP_COMPASS_CALIBRATION

    RE01 = re.compile(r' +Calibration date and time: ([/0-9: ]+)')
    RE04 = re.compile(r' +Bx +. +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) .')
    RE05 = re.compile(r' +By +. +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) .')
    RE06 = re.compile(r' +Bz +. +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) .')
    RE07 = re.compile(r' +Err +. +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) .')

    RE11 = re.compile(r' +. +([0-9e+-.]+) +.')
    RE12 = re.compile(r' +. +([0-9e+-.]+) +.')
    RE13 = re.compile(r' +. +([0-9e+-.]+) +.')
    RE14 = re.compile(r' +. +([0-9e+-.]+) +.')

    RE18 = re.compile(r' +. ([0-9.]+) .')
    RE21 = re.compile(r' +Calibration date and time: ([/0-9: ]+)')
    RE22 = re.compile(r' +Average Temperature During Calibration was +([0-9.]+) .')
    RE27 = re.compile(r' Roll +. +([0-9e+-.]+) +([0-9e+-.]+) +. +. +([0-9e+-.]+) +([0-9e+-.]+) +.')
    RE28 = re.compile(r' Pitch +. +([0-9e+-.]+) +([0-9e+-.]+) +. +. +([0-9e+-.]+) +([0-9e+-.]+) +.')
    RE32 = re.compile(r' Offset . +([0-9e+-.]+) +([0-9e+-.]+) +. +. +([0-9e+-.]+) +([0-9e+-.]+) +.')
    RE36 = re.compile(r' +Null +. (\d+) +.')

    def _build_parsed_values(self):
        log.error("ADCP_COMPASS_CALIBRATION_DataParticle 1")
        """
        """
        # Initialize
        matches = {}
        lines = self.raw_data.split(NEWLINE) # .replace(self.EF_CHAR,'#')
        match = self.RE01.match(lines[1])
        timestamp = match.group(1) # 9/14/2012  09:25:32
        matches[ADCP_COMPASS_CALIBRATION_KEY.FLUXGATE_CALIBRATION_TIMESTAMP] = time.mktime(time.strptime(timestamp, "%m/%d/%Y  %H:%M:%S"))

        match = self.RE04.match(lines[4])
        matches[ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BX] = [float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))]
        match = self.RE05.match(lines[5])
        matches[ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BY] = [float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))]
        match = self.RE06.match(lines[6])
        matches[ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BZ] = [float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))]
        match = self.RE07.match(lines[7])
        matches[ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_ERR] = [float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))]

        match = self.RE11.match(lines[11])
        matches[ADCP_COMPASS_CALIBRATION_KEY.COIL_OFFSET] = [float(match.group(1))]
        match = self.RE12.match(lines[12])
        matches[ADCP_COMPASS_CALIBRATION_KEY.COIL_OFFSET].append(float(match.group(1)))
        match = self.RE13.match(lines[13])
        matches[ADCP_COMPASS_CALIBRATION_KEY.COIL_OFFSET].append(float(match.group(1)))
        match = self.RE14.match(lines[14])
        matches[ADCP_COMPASS_CALIBRATION_KEY.COIL_OFFSET].append(float(match.group(1)))

        match = self.RE18.match(lines[18])
        matches[ADCP_COMPASS_CALIBRATION_KEY.ELECTRICAL_NULL] = float(match.group(1))

        match = self.RE21.match(lines[21])
        timestamp = match.group(1) # 9/14/2012  09:25:32
        matches[ADCP_COMPASS_CALIBRATION_KEY.TILT_CALIBRATION_TIMESTAMP] = time.mktime(time.strptime(timestamp, "%m/%d/%Y  %H:%M:%S"))

        match = self.RE22.match(lines[22])
        matches[ADCP_COMPASS_CALIBRATION_KEY.CALIBRATION_TEMP] = float(match.group(1))

        match = self.RE27.match(lines[27])
        matches[ADCP_COMPASS_CALIBRATION_KEY.ROLL_UP_DOWN] = [float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))]
        match = self.RE28.match(lines[28])
        matches[ADCP_COMPASS_CALIBRATION_KEY.PITCH_UP_DOWN] = [float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))]
        match = self.RE32.match(lines[32])
        matches[ADCP_COMPASS_CALIBRATION_KEY.OFFSET_UP_DOWN] = [float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))]

        match = self.RE36.match(lines[36])
        matches[ADCP_COMPASS_CALIBRATION_KEY.TILT_NULL] = float(match.group(1))

        result = []
        for (key, value) in matches.iteritems():
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: value})

        return result
