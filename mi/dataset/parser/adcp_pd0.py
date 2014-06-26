#!/usr/bin/env python

"""
@package mi.dataset.parser.adcp_pd0
@file marine-integrations/mi/dataset/parser/adcp_pd0.py
@author Jeff Roy
@brief Parser for the adcps_jln and moas_gl_adcpa dataset drivers
Release notes:

initial release
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'

import copy
import datetime as dt
import ntplib
import re
import struct

from calendar import timegm

from mi.core.log import get_logger

log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import \
    DataParticle, DataParticleKey, DataParticleValue
from mi.core.exceptions import SampleException, RecoverableSampleException, \
    DatasetParserException, UnexpectedDataException
from mi.dataset.dataset_parser import BufferLoadingParser

ADCPS_PD0_HEADER_REGEX = b'\x7f\x7f'  # header bytes in PD0 files flagged by 7F7F

ADCPS_PD0_HEADER_MATCHER = re.compile(ADCPS_PD0_HEADER_REGEX)

#define the lengths of ensemble parts
FIXED_HEADER_BYTES = 6
NUM_BYTES_BYTES = 2  # The number of bytes for the number of bytes field.
OFFSET_BYTES = 2
ID_BYTES = 2
ADCPS_FIXED_LEADER_BYTES = 59
ADCPA_FIXED_LEADER_BYTES = 58
ADCPS_VARIABLE_LEADER_BYTES = 65
ADCPA_VARIABLE_LEADER_BYTES = 60
VELOCITY_BYTES_PER_CELL = 8
CORRELATION_BYTES_PER_CELL = 4
ECHO_INTENSITY_BYTES_PER_CELL = 4
PERCENT_GOOD_BYTES_PER_CELL = 4
ADCPS_BOTTOM_TRACK_BYTES = 85
ADCPA_BOTTOM_TRACK_BYTES = 81
CHECKSUM_BYTES = 2

#used to verify 16 bit checksum
CHECKSUM_MODULO = 65535

#IDs of the different parts of the ensemble.
FIXED_LEADER_ID = 0
VARIABLE_LEADER_ID = 128
VELOCITY_ID = 256
CORRELATION_ID = 512
ECHO_INTENSITY_ID = 768
PERCENT_GOOD_ID = 1024
BOTTOM_TRACK_ID = 1536


class AdcpPd0ParserDataParticleKey(BaseEnum):
    """
    Data particles for the Teledyne ADCPs Workhorse PD0 formatted data files
    """

    # # Header Data
    # HEADER_ID = 'header_id'
    # DATA_SOURCE_ID = 'data_source_id'
    # NUM_BYTES = 'num_bytes'
    # NUM_DATA_TYPES = 'num_data_types'
    # OFFSET_DATA_TYPES = 'offset_data_types'
    #
    # # Fixed Leader Data
    # FIXED_LEADER_ID = 'fixed_leader_id'

    FIRMWARE_VERSION = 'firmware_version'
    FIRMWARE_REVISION = 'firmware_revision'
    SYSCONFIG_FREQUENCY = 'sysconfig_frequency'
    SYSCONFIG_BEAM_PATTERN = 'sysconfig_beam_pattern'
    SYSCONFIG_SENSOR_CONFIG = 'sysconfig_sensor_config'
    SYSCONFIG_HEAD_ATTACHED = 'sysconfig_head_attached'
    SYSCONFIG_VERTICAL_ORIENTATION = 'sysconfig_vertical_orientation'
    SYSCONFIG_BEAM_ANGLE = 'sysconfig_beam_angle'
    SYSCONFIG_BEAM_CONFIG = 'sysconfig_beam_config'
    DATA_FLAG = 'data_flag'
    LAG_LENGTH = 'lag_length'
    NUM_BEAMS = 'num_beams'
    NUM_CELLS = 'num_cells'
    PINGS_PER_ENSEMBLE = 'pings_per_ensemble'
    DEPTH_CELL_LENGTH = 'cell_length'
    BLANK_AFTER_TRANSMIT = 'blank_after_transmit'
    SIGNAL_PROCESSING_MODE = 'signal_processing_mode'
    LOW_CORR_THRESHOLD = 'low_corr_threshold'
    NUM_CODE_REPETITIONS = 'num_code_repetitions'
    PERCENT_GOOD_MIN = 'percent_good_min'
    ERROR_VEL_THRESHOLD = 'error_vel_threshold'
    TIME_PER_PING_MINUTES = 'time_per_ping_minutes'
    TIME_PER_PING_SECONDS = 'time_per_ping_seconds'
    COORD_TRANSFORM_TYPE = 'coord_transform_type'
    COORD_TRANSFORM_TILTS = 'coord_transform_tilts'
    COORD_TRANSFORM_BEAMS = 'coord_transform_beams'
    COORD_TRANSFORM_MAPPING = 'coord_transform_mapping'
    HEADING_ALIGNMENT = 'heading_alignment'
    HEADING_BIAS = 'heading_bias'
    SENSOR_SOURCE_SPEED = 'sensor_source_speed'
    SENSOR_SOURCE_DEPTH = 'sensor_source_depth'
    SENSOR_SOURCE_HEADING = 'sensor_source_heading'
    SENSOR_SOURCE_PITCH = 'sensor_source_pitch'
    SENSOR_SOURCE_ROLL = 'sensor_source_roll'
    SENSOR_SOURCE_CONDUCTIVITY = 'sensor_source_conductivity'
    SENSOR_SOURCE_TEMPERATURE = 'sensor_source_temperature'
    SENSOR_AVAILABLE_SPEED = 'sensor_available_speed'
    SENSOR_AVAILABLE_DEPTH = 'sensor_available_depth'
    SENSOR_AVAILABLE_HEADING = 'sensor_available_heading'
    SENSOR_AVAILABLE_PITCH = 'sensor_available_pitch'
    SENSOR_AVAILABLE_ROLL = 'sensor_available_roll'
    SENSOR_AVAILABLE_CONDUCTIVITY = 'sensor_available_conductivity'
    SENSOR_AVAILABLE_TEMPERATURE = 'sensor_available_temperature'
    BIN_1_DISTANCE = 'bin_1_distance'
    TRANSMIT_PULSE_LENGTH = 'transmit_pulse_length'
    REFERENCE_LAYER_START = 'reference_layer_start'
    REFERENCE_LAYER_STOP = 'reference_layer_stop'
    FALSE_TARGET_THRESHOLD = 'false_target_threshold'
    LOW_LATENCY_TRIGGER = 'low_latency_trigger'
    TRANSMIT_LAG_DISTANCE = 'transmit_lag_distance'
    CPU_SERIAL_NUM = 'cpu_board_serial_number'
    SYSTEM_BANDWIDTH = 'system_bandwidth'
    SYSTEM_POWER = 'system_power'
    SERIAL_NUMBER = 'serial_number'
    BEAM_ANGLE = 'beam_angle'

    # Variable Leader Data
    #VARIABLE_LEADER_ID = 'variable_leader_id'
    ENSEMBLE_NUMBER = 'ensemble_number'
    REAL_TIME_CLOCK = 'real_time_clock'
    ENSEMBLE_START_TIME = 'ensemble_start_time'
    ENSEMBLE_NUMBER_INCREMENT = 'ensemble_number_increment'
    BIT_RESULT_DEMOD_1 = 'bit_result_demod_1'
    BIT_RESULT_DEMOD_0 = 'bit_result_demod_0'
    BIT_RESULT_TIMING = 'bit_result_timing'
    SPEED_OF_SOUND = 'speed_of_sound'
    TRANSDUCER_DEPTH = 'transducer_depth'
    HEADING = 'heading'
    PITCH = 'pitch'
    ROLL = 'roll'
    SALINITY = 'salinity'
    TEMPERATURE = 'temperature'
    MPT_MINUTES = 'mpt_minutes'
    MPT_SECONDS = 'mpt_seconds'
    HEADING_STDEV = 'heading_stdev'
    PITCH_STDEV = 'pitch_stdev'
    ROLL_STDEV = 'roll_stdev'
    ADC_TRANSMIT_CURRENT = 'adc_transmit_current'
    ADC_TRANSMIT_VOLTAGE = 'adc_transmit_voltage'
    ADC_AMBIENT_TEMP = 'adc_ambient_temp'
    ADC_PRESSURE_PLUS = 'adc_pressure_plus'
    ADC_PRESSURE_MINUS = 'adc_pressure_minus'
    ADC_ATTITUDE_TEMP = 'adc_attitude_temp'
    ADC_ATTITUDE = 'adc_attitude'
    ADC_CONTAMINATION_SENSOR = 'adc_contamination_sensor'
    BUS_ERROR_EXCEPTION = 'bus_error_exception'
    ADDRESS_ERROR_EXCEPTION = 'address_error_exception'
    ILLEGAL_INSTRUCTION_EXCEPTION = 'illegal_instruction_exception'
    ZERO_DIVIDE_INSTRUCTION = 'zero_divide_instruction'
    EMULATOR_EXCEPTION = 'emulator_exception'
    UNASSIGNED_EXCEPTION = 'unassigned_exception'
    WATCHDOG_RESTART_OCCURRED = 'watchdog_restart_occurred'
    BATTERY_SAVER_POWER = 'battery_saver_power'
    PINGING = 'pinging'
    COLD_WAKEUP_OCCURRED = 'cold_wakeup_occurred'
    UNKNOWN_WAKEUP_OCCURRED = 'unknown_wakeup_occurred'
    CLOCK_READ_ERROR = 'clock_read_error'
    UNEXPECTED_ALARM = 'unexpected_alarm'
    CLOCK_JUMP_FORWARD = 'clock_jump_forward'
    CLOCK_JUMP_BACKWARD = 'clock_jump_backward'
    POWER_FAIL = 'power_fail'
    SPURIOUS_DSP_INTERRUPT = 'spurious_dsp_interrupt'
    SPURIOUS_UART_INTERRUPT = 'spurious_uart_interrupt'
    SPURIOUS_CLOCK_INTERRUPT = 'spurious_clock_interrupt'
    LEVEL_7_INTERRUPT = 'level_7_interrupt'
    PRESSURE = 'pressure'
    PRESSURE_VARIANCE = 'pressure_variance'

    REAL_TIME_CLOCK2 = 'real_time_clock_2'
    ENSEMBLE_START_TIME2 = 'ensemble_start_time_2'

    # Velocity Data
    #VELOCITY_DATA_ID = 'velocity_data_id'
    WATER_VELOCITY_EAST = 'water_velocity_east'
    WATER_VELOCITY_NORTH = 'water_velocity_north'
    WATER_VELOCITY_UP = 'water_velocity_up'
    ERROR_VELOCITY = 'error_velocity'

    # Correlation Magnitude Data
    #CORRELATION_MAGNITUDE_ID = 'correlation_magnitude_id'
    CORRELATION_MAGNITUDE_BEAM1 = 'correlation_magnitude_beam1'
    CORRELATION_MAGNITUDE_BEAM2 = 'correlation_magnitude_beam2'
    CORRELATION_MAGNITUDE_BEAM3 = 'correlation_magnitude_beam3'
    CORRELATION_MAGNITUDE_BEAM4 = 'correlation_magnitude_beam4'

    # Echo Intensity Data
    #ECHO_INTENSITY_ID = 'echo_intensity_id'
    ECHO_INTENSITY_BEAM1 = 'echo_intensity_beam1'
    ECHO_INTENSITY_BEAM2 = 'echo_intensity_beam2'
    ECHO_INTENSITY_BEAM3 = 'echo_intensity_beam3'
    ECHO_INTENSITY_BEAM4 = 'echo_intensity_beam4'

    # Percent Good Data
    #PERCENT_GOOD_ID = 'percent_good_id'
    PERCENT_GOOD_3BEAM = 'percent_good_3beam'
    PERCENT_TRANSFORMS_REJECT = 'percent_transforms_reject'
    PERCENT_BAD_BEAMS = 'percent_bad_beams'
    PERCENT_GOOD_4BEAM = 'percent_good_4beam'

    # Bottom Track Data (only produced if Adcpa is in less than 65 m of water)
    #BOTTOM_TRACK_ID = 'bottom_track_id'
    BT_PINGS_PER_ENSEMBLE = 'bt_pings_per_ensemble'
    BT_DELAY_BEFORE_REACQUIRE = 'bt_delay_before_reacquire'
    BT_CORR_MAGNITUDE_MIN = 'bt_corr_magnitude_min'
    BT_EVAL_MAGNITUDE_MIN = 'bt_eval_magnitude_min'
    BT_PERCENT_GOOD_MIN = 'bt_percent_good_min'
    BT_MODE = 'bt_mode'
    BT_ERROR_VELOCITY_MAX = 'bt_error_velocity_max'

    BT_BEAM1_RANGE = 'bt_beam1_range'
    BT_BEAM2_RANGE = 'bt_beam2_range'
    BT_BEAM3_RANGE = 'bt_beam3_range'
    BT_BEAM4_RANGE = 'bt_beam4_range'

    BT_EASTWARD_VELOCITY = 'bt_eastward_velocity'
    BT_NORTHWARD_VELOCITY = 'bt_northward_velocity'
    BT_UPWARD_VELOCITY = 'bt_upward_velocity'
    BT_ERROR_VELOCITY = 'bt_error_velocity'
    BT_BEAM1_CORRELATION = 'bt_beam1_correlation'
    BT_BEAM2_CORRELATION = 'bt_beam2_correlation'
    BT_BEAM3_CORRELATION = 'bt_beam3_correlation'
    BT_BEAM4_CORRELATION = 'bt_beam4_correlation'
    BT_BEAM1_EVAL_AMP = 'bt_beam1_eval_amp'
    BT_BEAM2_EVAL_AMP = 'bt_beam2_eval_amp'
    BT_BEAM3_EVAL_AMP = 'bt_beam3_eval_amp'
    BT_BEAM4_EVAL_AMP = 'bt_beam4_eval_amp'
    BT_BEAM1_PERCENT_GOOD = 'bt_beam1_percent_good'
    BT_BEAM2_PERCENT_GOOD = 'bt_beam2_percent_good'
    BT_BEAM3_PERCENT_GOOD = 'bt_beam3_percent_good'
    BT_BEAM4_PERCENT_GOOD = 'bt_beam4_percent_good'
    BT_REF_LAYER_MIN = 'bt_ref_layer_min'
    BT_REF_LAYER_NEAR = 'bt_ref_layer_near'
    BT_REF_LAYER_FAR = 'bt_ref_layer_far'
    BT_EASTWARD_REF_LAYER_VELOCITY = 'bt_eastward_ref_layer_velocity'
    BT_NORTHWARD_REF_LAYER_VELOCITY = 'bt_northward_ref_layer_velocity'
    BT_UPWARD_REF_LAYER_VELOCITY = 'bt_upward_ref_layer_velocity'
    BT_ERROR_REF_LAYER_VELOCITY = 'bt_error_ref_layer_velocity'
    BT_BEAM1_REF_CORRELATION = 'bt_beam1_ref_correlation'
    BT_BEAM2_REF_CORRELATION = 'bt_beam2_ref_correlation'
    BT_BEAM3_REF_CORRELATION = 'bt_beam3_ref_correlation'
    BT_BEAM4_REF_CORRELATION = 'bt_beam4_ref_correlation'
    BT_BEAM1_REF_INTENSITY = 'bt_beam1_ref_intensity'
    BT_BEAM2_REF_INTENSITY = 'bt_beam2_ref_intensity'
    BT_BEAM3_REF_INTENSITY = 'bt_beam3_ref_intensity'
    BT_BEAM4_REF_INTENSITY = 'bt_beam4_ref_intensity'
    BT_BEAM1_REF_PERCENT_GOOD = 'bt_beam1_ref_percent_good'
    BT_BEAM2_REF_PERCENT_GOOD = 'bt_beam2_ref_percent_good'
    BT_BEAM3_REF_PERCENT_GOOD = 'bt_beam3_ref_percent_good'
    BT_BEAM4_REF_PERCENT_GOOD = 'bt_beam4_ref_percent_good'
    BT_MAX_DEPTH = 'bt_max_depth'
    BT_BEAM1_RSSI_AMPLITUDE = 'bt_beam1_rssi_amplitude'
    BT_BEAM2_RSSI_AMPLITUDE = 'bt_beam2_rssi_amplitude'
    BT_BEAM3_RSSI_AMPLITUDE = 'bt_beam3_rssi_amplitude'
    BT_BEAM4_RSSI_AMPLITUDE = 'bt_beam4_rssi_amplitude'
    BT_GAIN = 'bt_gain'

    # Ensemble checksum
    #CHECKSUM = 'checksum'


class StateKey(BaseEnum):
    POSITION = 'position'  # number of bytes read


class AdcpFileType(BaseEnum):
    #enumeration of the different PD0 file formats
    ADCPA_FILE = 'adcpa_file'  # ADCPA PD0 files are used by the ExplorerDVL instruments
    ADCPS_File = 'adcps_file'  # ADCPS(T) PD0 files are used by the Workhorse LongRanger Monitor


class AdcpPd0DataParticle(DataParticle):
    """
    Intermediate particle class to handle particle streams from PD0 files
    constructor must be passed a valid file_type from the enumeration AdcpFileType
    All other constructor parameters handled by base class
    """

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None,
                 file_type=None):

        self._file_type = file_type
        # file_type must be set to a value in AdcpFileType
        # used for conditional decoding of the raw data in
        # _build_parsed_values

        super(AdcpPd0DataParticle, self).__init__(raw_data,
                                                  port_timestamp,
                                                  internal_timestamp,
                                                  preferred_timestamp,
                                                  quality_flag,
                                                  new_sequence)

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """

        self.final_result = []

        #set particle type specifics
        if self._file_type == AdcpFileType.ADCPA_FILE:
            fixed_leader_bytes = ADCPA_FIXED_LEADER_BYTES
            variable_leader_bytes = ADCPA_VARIABLE_LEADER_BYTES
            bottom_track_bytes = ADCPA_BOTTOM_TRACK_BYTES
        elif self._file_type == AdcpFileType.ADCPS_File:
            fixed_leader_bytes = ADCPS_FIXED_LEADER_BYTES
            variable_leader_bytes = ADCPS_VARIABLE_LEADER_BYTES
            bottom_track_bytes = ADCPS_BOTTOM_TRACK_BYTES
        else:
            raise SampleException('invalid file type')

        #parse the file header
        (header_id, data_source_id, num_bytes, spare, num_data_types) = \
            struct.unpack_from('<BBHBB', self.raw_data)

        #log.debug("_build_parsed_values Number of data types = %d", num_data_types )

        offsets = []  # create list for offsets
        start = FIXED_HEADER_BYTES  # offsets start at byte 6 (using 0 indexing)
        data_types_idx = 1  # counter for n data types
        fixed_leader_found = False

        while data_types_idx <= num_data_types:
            value = struct.unpack_from('<H', self.raw_data, start)[0]

            #log.debug("_build_parsed_values Offset for data type %d is %d ", num_data_types, value )
            offsets.append(value)
            start += NUM_BYTES_BYTES
            data_types_idx += 1

        for offset in offsets:
            # for each offset, using the starting byte, determine the data type
            # and then parse accordingly.
            data_type = struct.unpack_from('<H', self.raw_data, offset)[0]

            #log.debug("_build_parsed_values Processing at byte %d", offset)
            #log.debug("_build_parsed_values ID is %d", data_type)

            # fixed leader data (x00x00)
            if data_type == FIXED_LEADER_ID:
                data = self.raw_data[offset:offset + fixed_leader_bytes]
                self.parse_fixed_leader(data)
                fixed_leader_found = True
                num_cells = self.num_depth_cells  # grab the # of depth cells
                # obtained from the fixed leader
                # data type

            # variable leader data (x80x00)
            elif data_type == VARIABLE_LEADER_ID:
                data = self.raw_data[offset:offset + variable_leader_bytes]
                self.parse_variable_leader(data)

            # velocity data (x00x01)
            elif data_type == VELOCITY_ID:

                if not fixed_leader_found:
                    raise RecoverableSampleException("No Fixed leader")

                # number of bytes is a function of the user selectable number of
                # depth cells (WN command), calculated above
                num_bytes = ID_BYTES + VELOCITY_BYTES_PER_CELL * num_cells
                data = self.raw_data[offset:offset + num_bytes]
                self.parse_velocity_data(data)

            # correlation magnitude data (x00x02)
            elif data_type == CORRELATION_ID:
                if not fixed_leader_found:
                    raise RecoverableSampleException("No Fixed leader")

                # number of bytes is a function of the user selectable number of
                # depth cells (WN command), calculated above
                num_bytes = ID_BYTES + CORRELATION_BYTES_PER_CELL * num_cells
                data = self.raw_data[offset:offset + num_bytes]
                self.parse_correlation_magnitude_data(data)

            # echo intensity data (x00x03)
            elif data_type == ECHO_INTENSITY_ID:
                if not fixed_leader_found:
                    raise RecoverableSampleException("No Fixed leader")

                # number of bytes is a function of the user selectable number of
                # depth cells (WN command), calculated above
                num_bytes = ID_BYTES + ECHO_INTENSITY_BYTES_PER_CELL * num_cells
                data = self.raw_data[offset:offset + num_bytes]
                self.parse_echo_intensity_data(data)

            # percent-good data (x00x04)
            elif data_type == PERCENT_GOOD_ID:
                if not fixed_leader_found:
                    raise RecoverableSampleException("No Fixed leader")

                # number of bytes is a function of the user selectable number of
                # depth cells (WN command), calculated above
                num_bytes = ID_BYTES + PERCENT_GOOD_BYTES_PER_CELL * num_cells
                data = self.raw_data[offset:offset + num_bytes]
                self.parse_percent_good_data(data)

            # bottom track data (x00x06)
            elif data_type == BOTTOM_TRACK_ID:
                if not fixed_leader_found:
                    raise RecoverableSampleException("No Fixed leader")

                data = self.raw_data[offset:offset + bottom_track_bytes]
                self.parse_bottom_track_data(data)
            else:
                raise RecoverableSampleException("unrecognized ID")
        return self.final_result

    def parse_fixed_leader(self, data):
        """
        Parse the fixed leader portion of the particle
       """
        (fixed_leader_id, firmware_version, firmware_revision,
         sysconfig_lsb, sysconfig_msb, data_flag, lag_length, num_beams, num_cells,
         pings_per_ensemble, depth_cell_length, blank_after_transmit,
         signal_processing_mode, low_corr_threshold, num_code_repetitions,
         percent_good_min, error_vel_threshold, time_per_ping_minutes,
         time_per_ping_seconds, time_per_ping_hundredths, coord_transform_type,
         heading_alignment, heading_bias, sensor_source, sensor_available,
         bin_1_distance, transmit_pulse_length, reference_layer_start,
         reference_layer_stop, false_target_threshold, low_latency_trigger,
         transmit_lag_distance, cpu_serial_num, system_bandwidth,
         system_power, SPARE2, serial_number) = \
            struct.unpack_from('<H8B3H4BH4B2h2B2H4BHQH2BI', data)

        # store the number of depth cells for use elsewhere
        self.num_depth_cells = num_cells

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.FIRMWARE_VERSION,
                                                    firmware_version, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.FIRMWARE_REVISION,
                                                    firmware_revision, int))

        frequencies = [75, 150, 300, 600, 1200, 2400]

        #following items all pulled from the sys config LSB
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SYSCONFIG_FREQUENCY,
                                                    frequencies[sysconfig_lsb & 0b00000111], int))
        #bitwise and to extract the frequency index
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SYSCONFIG_BEAM_PATTERN,
                                                    1 if sysconfig_lsb & 0b00001000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SYSCONFIG_SENSOR_CONFIG,
                                                    (sysconfig_lsb & 0b00110000) >> 4, int))
        #bitwise right shift 4 bits
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SYSCONFIG_HEAD_ATTACHED,
                                                    1 if sysconfig_lsb & 0b01000000 else 0, int))
        self.final_result.append(
            self._encode_value(AdcpPd0ParserDataParticleKey.SYSCONFIG_VERTICAL_ORIENTATION,
                               1 if sysconfig_lsb & 0b10000000 else 0, int))

        #following items all pulled from the sys config MSB
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SYSCONFIG_BEAM_ANGLE,
                                                    sysconfig_msb & 0b00000011, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SYSCONFIG_BEAM_CONFIG,
                                                    (sysconfig_msb & 0b11110000) >> 4, int))
        #bitwise right shift 4 bits note: must do the and first then shift

        if 0 != data_flag:
            raise RecoverableSampleException("real/sim data_flag was not equal to 0")

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.DATA_FLAG,
                                                    data_flag, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.LAG_LENGTH,
                                                    lag_length, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.NUM_BEAMS,
                                                    num_beams, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.NUM_CELLS,
                                                    num_cells, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.PINGS_PER_ENSEMBLE,
                                                    pings_per_ensemble, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.DEPTH_CELL_LENGTH,
                                                    depth_cell_length, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BLANK_AFTER_TRANSMIT,
                                                    blank_after_transmit, int))

        if 1 != signal_processing_mode:
            raise RecoverableSampleException("signal_processing_mode was not equal to 1")

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SIGNAL_PROCESSING_MODE,
                                                    signal_processing_mode, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.LOW_CORR_THRESHOLD,
                                                    low_corr_threshold, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.NUM_CODE_REPETITIONS,
                                                    num_code_repetitions, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.PERCENT_GOOD_MIN,
                                                    percent_good_min, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ERROR_VEL_THRESHOLD,
                                                    error_vel_threshold, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.TIME_PER_PING_MINUTES,
                                                    time_per_ping_minutes, int))

        tpp_float_seconds = time_per_ping_seconds + (time_per_ping_hundredths / 100.0)
        #combine seconds and hundreds into a float
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.TIME_PER_PING_SECONDS,
                                                    tpp_float_seconds, float))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.COORD_TRANSFORM_TYPE,
                                                    (coord_transform_type & 0b00011000) >> 3, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.COORD_TRANSFORM_TILTS,
                                                    1 if coord_transform_type & 0b00000100 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.COORD_TRANSFORM_BEAMS,
                                                    1 if coord_transform_type & 0b0000010 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.COORD_TRANSFORM_MAPPING,
                                                    1 if coord_transform_type & 0b00000001 else 0, int))

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.HEADING_ALIGNMENT,
                                                    heading_alignment, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.HEADING_BIAS,
                                                    heading_bias, int))

        #pull the following out of the sensor source byte
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_SOURCE_SPEED,
                                                    1 if sensor_source & 0b01000000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_SOURCE_DEPTH,
                                                    1 if sensor_source & 0b00100000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_SOURCE_HEADING,
                                                    1 if sensor_source & 0b00010000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_SOURCE_PITCH,
                                                    1 if sensor_source & 0b00001000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_SOURCE_ROLL,
                                                    1 if sensor_source & 0b00000100 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_SOURCE_CONDUCTIVITY,
                                                    1 if sensor_source & 0b00000010 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_SOURCE_TEMPERATURE,
                                                    1 if sensor_source & 0b00000001 else 0, int))

        #pull the following out of the sensor available byte
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_AVAILABLE_SPEED,
                                                    1 if sensor_available & 0b01000000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_AVAILABLE_DEPTH,
                                                    1 if sensor_available & 0b00100000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_AVAILABLE_HEADING,
                                                    1 if sensor_available & 0b00010000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_AVAILABLE_PITCH,
                                                    1 if sensor_available & 0b00001000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_AVAILABLE_ROLL,
                                                    1 if sensor_available & 0b00000100 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_AVAILABLE_CONDUCTIVITY,
                                                    1 if sensor_available & 0b00000010 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SENSOR_AVAILABLE_TEMPERATURE,
                                                    1 if sensor_available & 0b00000001 else 0, int))

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BIN_1_DISTANCE,
                                                    bin_1_distance, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.TRANSMIT_PULSE_LENGTH,
                                                    transmit_pulse_length, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.REFERENCE_LAYER_START,
                                                    reference_layer_start, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.REFERENCE_LAYER_STOP,
                                                    reference_layer_stop, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.FALSE_TARGET_THRESHOLD,
                                                    false_target_threshold, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.LOW_LATENCY_TRIGGER,
                                                    low_latency_trigger, int))
        #this is "SPARE" byte in vendor doc, see comments
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.TRANSMIT_LAG_DISTANCE,
                                                    transmit_lag_distance, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SYSTEM_BANDWIDTH,
                                                    system_bandwidth, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SERIAL_NUMBER,
                                                    serial_number, int))

        #following parameters only exist in ADCPS_JLN_INSTRUMENT particles
        if self._file_type == AdcpFileType.ADCPS_File:
            self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.CPU_SERIAL_NUM,
                                                        cpu_serial_num, int))
            self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SYSTEM_POWER,
                                                        system_power, int))
            beam_angle = struct.unpack('<B', data[-1:])[0]  # beam angle is last byte
            self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BEAM_ANGLE,
                                                        beam_angle, int))

    def parse_variable_leader(self, data):
        """
        Parse the variable leader portion of the particle
        """
        rtc = {}
        rtc2 = {}

        (variable_leader_id, ensemble_number, rtc['year'], rtc['month'],
         rtc['day'], rtc['hour'], rtc['minute'], rtc['second'],
         rtc['hundredths'], ensemble_number_increment, error_bit_field,
         reserved_error_bit_field, speed_of_sound, transducer_depth, heading,
         pitch, roll, salinity, temperature, mpt_minutes, mpt_seconds_component,
         mpt_hundredths_component, heading_stdev, pitch_stdev, roll_stdev,
         adc_transmit_current, adc_transmit_voltage, adc_ambient_temp,
         adc_pressure_plus, adc_pressure_minus, adc_attitude_temp,
         adc_attitiude, adc_contamination_sensor, error_status_word_1,
         error_status_word_2, error_status_word_3, error_status_word_4,
         SPARE1, pressure, pressure_variance, SPARE2) = \
            struct.unpack_from('<2H10B3H2hHh18BH2II', data)
            #Note: the ADCPS leader has extra bytes at end, handled lower in method

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ENSEMBLE_NUMBER,
                                                    ensemble_number, int))

        # convert individual date and time values to datetime object and
        # calculate the NTP timestamp (seconds since Jan 1, 1900), per OOI
        # convention
        dts = dt.datetime(2000 + rtc['year'], rtc['month'], rtc['day'],
                          rtc['hour'], rtc['minute'], rtc['second'])
        epoch_ts = timegm(dts.timetuple()) + (rtc['hundredths'] / 100.0)  # seconds since 1970-01-01 in UTC
        ntp_ts = ntplib.system_to_ntp_time(epoch_ts)

        self.set_internal_timestamp(ntp_ts)

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.REAL_TIME_CLOCK,
                                                    [rtc['year'], rtc['month'], rtc['day'],
                                                     rtc['hour'], rtc['minute'], rtc['second'],
                                                     rtc['hundredths']], list))
        #IDD calls for array of 8, may need to hard code century

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ENSEMBLE_START_TIME,
                                                    ntp_ts, float))

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ENSEMBLE_NUMBER_INCREMENT,
                                                    ensemble_number_increment, int))

        #decode the BIT test byte
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BIT_RESULT_DEMOD_1,
                                                    1 if error_bit_field & 0b00010000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BIT_RESULT_DEMOD_0,
                                                    1 if error_bit_field & 0b00001000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BIT_RESULT_TIMING,
                                                    1 if error_bit_field & 0b00000010 else 0, int))

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SPEED_OF_SOUND,
                                                    speed_of_sound, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.TRANSDUCER_DEPTH,
                                                    transducer_depth, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.HEADING,
                                                    heading, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.PITCH,
                                                    pitch, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ROLL,
                                                    roll, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SALINITY,
                                                    salinity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.TEMPERATURE,
                                                    temperature, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.MPT_MINUTES,
                                                    mpt_minutes, int))

        mpt_seconds = float(mpt_seconds_component + (mpt_hundredths_component / 100.0))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.MPT_SECONDS,
                                                    mpt_seconds, float))

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.HEADING_STDEV,
                                                    heading_stdev, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.PITCH_STDEV,
                                                    pitch_stdev, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ROLL_STDEV,
                                                    roll_stdev, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ADC_TRANSMIT_CURRENT,
                                                    adc_transmit_current, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ADC_TRANSMIT_VOLTAGE,
                                                    adc_transmit_voltage, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ADC_AMBIENT_TEMP,
                                                    adc_ambient_temp, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ADC_PRESSURE_PLUS,
                                                    adc_pressure_plus, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ADC_PRESSURE_MINUS,
                                                    adc_pressure_minus, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ADC_ATTITUDE_TEMP,
                                                    adc_attitude_temp, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ADC_ATTITUDE,
                                                    adc_attitiude, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ADC_CONTAMINATION_SENSOR,
                                                    adc_contamination_sensor, int))

        #decode the error status bytes
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BUS_ERROR_EXCEPTION,
                                                    1 if error_status_word_1 & 0b00000001 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ADDRESS_ERROR_EXCEPTION,
                                                    1 if error_status_word_1 & 0b00000010 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ILLEGAL_INSTRUCTION_EXCEPTION,
                                                    1 if error_status_word_1 & 0b00000100 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ZERO_DIVIDE_INSTRUCTION,
                                                    1 if error_status_word_1 & 0b00001000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.EMULATOR_EXCEPTION,
                                                    1 if error_status_word_1 & 0b00010000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.UNASSIGNED_EXCEPTION,
                                                    1 if error_status_word_1 & 0b00100000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.WATCHDOG_RESTART_OCCURRED,
                                                    1 if error_status_word_1 & 0b01000000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BATTERY_SAVER_POWER,
                                                    1 if error_status_word_1 & 0b10000000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.PINGING,
                                                    1 if error_status_word_2 & 0b00000001 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.COLD_WAKEUP_OCCURRED,
                                                    1 if error_status_word_2 & 0b01000000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.UNKNOWN_WAKEUP_OCCURRED,
                                                    1 if error_status_word_2 & 0b10000000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.CLOCK_READ_ERROR,
                                                    1 if error_status_word_3 & 0b00000001 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.UNEXPECTED_ALARM,
                                                    1 if error_status_word_3 & 0b00000010 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.CLOCK_JUMP_FORWARD,
                                                    1 if error_status_word_3 & 0b00000100 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.CLOCK_JUMP_BACKWARD,
                                                    1 if error_status_word_3 & 0b00001000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.POWER_FAIL,
                                                    1 if error_status_word_4 & 0b00001000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SPURIOUS_DSP_INTERRUPT,
                                                    1 if error_status_word_4 & 0b00010000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SPURIOUS_UART_INTERRUPT,
                                                    1 if error_status_word_4 & 0b00100000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.SPURIOUS_CLOCK_INTERRUPT,
                                                    1 if error_status_word_4 & 0b01000000 else 0, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.LEVEL_7_INTERRUPT,
                                                    1 if error_status_word_4 & 0b10000000 else 0, int))

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.PRESSURE,
                                                    pressure, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.PRESSURE_VARIANCE,
                                                    pressure_variance, int))

        if self._file_type == AdcpFileType.ADCPS_File:
            #RTC2 values are last 8 bytes when provided
            (rtc2['century'], rtc2['year'], rtc2['month'],
             rtc2['day'], rtc2['hour'], rtc2['minute'], rtc2['second'],
             rtc2['hundredths']) = struct.unpack('<8B', data[-8:])

            dts = dt.datetime(rtc2['century'] * 100 + rtc2['year'], rtc2['month'], rtc2['day'],
                              rtc2['hour'], rtc2['minute'], rtc2['second'])

            epoch_ts = timegm(dts.timetuple()) + (rtc2['hundredths'] / 100.0)  # seconds since 1970-01-01 in UTC
            ntp_ts = ntplib.system_to_ntp_time(epoch_ts)

            self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.REAL_TIME_CLOCK2,
                                                        [rtc2['century'], rtc['year'], rtc['month'], rtc['day'],
                                                         rtc['hour'], rtc['minute'], rtc['second'],
                                                         rtc['hundredths']], list))

            self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ENSEMBLE_START_TIME2,
                                                        ntp_ts, float))

    def parse_velocity_data(self, data):
        """
        Parse the velocity portion of the particle
        """
        num_cells = self.num_depth_cells
        offset = ID_BYTES

        water_velocity_east = []
        water_velocity_north = []
        water_velocity_up = []
        error_velocity = []
        for row in range(0, num_cells):
            (a, b, c, d) = struct.unpack_from('<4h', data, offset)
            water_velocity_east.append(a)
            water_velocity_north.append(b)
            water_velocity_up.append(c)
            error_velocity.append(d)
            offset += VELOCITY_BYTES_PER_CELL

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.WATER_VELOCITY_EAST,
                                                    water_velocity_east, list))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.WATER_VELOCITY_NORTH,
                                                    water_velocity_north, list))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.WATER_VELOCITY_UP,
                                                    water_velocity_up, list))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ERROR_VELOCITY,
                                                    error_velocity, list))

    def parse_correlation_magnitude_data(self, data):
        """
        Parse the correlation magnitude portion of the particle
        """
        num_cells = self.num_depth_cells
        offset = ID_BYTES

        correlation_magnitude_beam1 = []
        correlation_magnitude_beam2 = []
        correlation_magnitude_beam3 = []
        correlation_magnitude_beam4 = []
        for row in range(0, num_cells):
            (a, b, c, d) = struct.unpack_from('<4B', data, offset)
            correlation_magnitude_beam1.append(a)
            correlation_magnitude_beam2.append(b)
            correlation_magnitude_beam3.append(c)
            correlation_magnitude_beam4.append(d)
            offset += CORRELATION_BYTES_PER_CELL

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.CORRELATION_MAGNITUDE_BEAM1,
                                                    correlation_magnitude_beam1, list))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.CORRELATION_MAGNITUDE_BEAM2,
                                                    correlation_magnitude_beam2, list))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.CORRELATION_MAGNITUDE_BEAM3,
                                                    correlation_magnitude_beam3, list))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.CORRELATION_MAGNITUDE_BEAM4,
                                                    correlation_magnitude_beam4, list))

    def parse_echo_intensity_data(self, data):
        """
        Parse the echo intensity portion of the particle
        """
        num_cells = self.num_depth_cells
        offset = ID_BYTES

        echo_intesity_beam1 = []
        echo_intesity_beam2 = []
        echo_intesity_beam3 = []
        echo_intesity_beam4 = []
        for row in range(0, num_cells):
            (a, b, c, d) = struct.unpack_from('<4B', data, offset)
            echo_intesity_beam1.append(a)
            echo_intesity_beam2.append(b)
            echo_intesity_beam3.append(c)
            echo_intesity_beam4.append(d)
            offset += ECHO_INTENSITY_BYTES_PER_CELL

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ECHO_INTENSITY_BEAM1,
                                                    echo_intesity_beam1, list))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ECHO_INTENSITY_BEAM2,
                                                    echo_intesity_beam2, list))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ECHO_INTENSITY_BEAM3,
                                                    echo_intesity_beam3, list))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.ECHO_INTENSITY_BEAM4,
                                                    echo_intesity_beam4, list))

    def parse_percent_good_data(self, data):
        """
        Parse the percent good portion of the particle

        @throws RecoverableSampleException If there is a problem with sample creation
        """
        num_cells = self.num_depth_cells
        offset = ID_BYTES

        percent_good_3beam = []
        percent_transforms_reject = []
        percent_bad_beams = []
        percent_good_4beam = []
        for row in range(0, num_cells):
            (a, b, c, d) = struct.unpack_from('<4B', data, offset)
            percent_good_3beam.append(a)
            percent_transforms_reject.append(b)
            percent_bad_beams.append(c)
            percent_good_4beam.append(d)
            offset += PERCENT_GOOD_BYTES_PER_CELL

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.PERCENT_GOOD_3BEAM,
                                                    percent_good_3beam, list))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.PERCENT_TRANSFORMS_REJECT,
                                                    percent_transforms_reject, list))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.PERCENT_BAD_BEAMS,
                                                    percent_bad_beams, list))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.PERCENT_GOOD_4BEAM,
                                                    percent_good_4beam, list))

    def parse_bottom_track_data(self, data):
        """
        Parse the bottom track portion of the particle

        @throws RecoverableSampleException If there is a problem with sample creation
        """

        log.info("*** parse_bottom_track_data called***")
        #info statement to find a record with bottom track data!

        (bottom_track_id, bt_pings_per_ensemble, bt_delay_before_reacquire,
         bt_corr_magnitude_min, bt_amp_magnitude_min, bt_percent_good_min,
         bt_mode, bt_error_velocity_max, RESERVED, beam1_bt_range_lsb, beam2_bt_range_lsb,
         beam3_bt_range_lsb, beam4_bt_range_lsb, eastward_bt_velocity,
         northward_bt_velocity, upward_bt_velocity, error_bt_velocity,
         beam1_bt_correlation, beam2_bt_correlation, beam3_bt_correlation,
         beam4_bt_correlation, beam1_eval_amp, beam2_eval_amp, beam3_eval_amp,
         beam4_eval_amp, beam1_bt_percent_good, beam2_bt_percent_good,
         beam3_bt_percent_good, beam4_bt_percent_good, ref_layer_min,
         ref_layer_near, ref_layer_far, beam1_ref_layer_velocity,
         beam2_ref_layer_velocity, beam3_ref_layer_velocity,
         beam4_ref_layer_velocity, beam1_ref_correlation, beam2_ref_correlation,
         beam3_ref_correlation, beam4_ref_correlation, beam1_ref_intensity,
         beam2_ref_intensity, beam3_ref_intensity, beam4_ref_intensity,
         beam1_ref_percent_good, beam2_ref_percent_good, beam3_ref_percent_good,
         beam4_ref_percent_good, bt_max_depth, beam1_rssi_amplitude,
         beam2_rssi_amplitude, beam3_rssi_amplitude, beam4_rssi_amplitude,
         bt_gain, beam1_bt_range_msb, beam2_bt_range_msb, beam3_bt_range_msb,
         beam4_bt_range_msb) = \
            struct.unpack_from('<3H4BHL4H4h12B3H4h12BH9B', data)
            #Note, ADCPS has 4 additional reserved bytes at the end, which are
            #not needed for either particle

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_PINGS_PER_ENSEMBLE,
                                                    bt_pings_per_ensemble, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_DELAY_BEFORE_REACQUIRE,
                                                    bt_delay_before_reacquire, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_CORR_MAGNITUDE_MIN,
                                                    bt_corr_magnitude_min, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_EVAL_MAGNITUDE_MIN,
                                                    bt_amp_magnitude_min, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_PERCENT_GOOD_MIN,
                                                    bt_percent_good_min, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_MODE,
                                                    bt_mode, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_ERROR_VELOCITY_MAX,
                                                    bt_error_velocity_max, int))

        #need to combine LSBs and MSBs of ranges
        beam1_bt_range = beam1_bt_range_lsb + (beam1_bt_range_msb << 16)
        beam2_bt_range = beam2_bt_range_lsb + (beam2_bt_range_msb << 16)
        beam3_bt_range = beam3_bt_range_lsb + (beam3_bt_range_msb << 16)
        beam4_bt_range = beam4_bt_range_lsb + (beam4_bt_range_msb << 16)

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM1_RANGE,
                                                    beam1_bt_range, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM2_RANGE,
                                                    beam2_bt_range, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM3_RANGE,
                                                    beam3_bt_range, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM4_RANGE,
                                                    beam4_bt_range, int))

        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_EASTWARD_VELOCITY,
                                                    eastward_bt_velocity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_NORTHWARD_VELOCITY,
                                                    northward_bt_velocity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_UPWARD_VELOCITY,
                                                    upward_bt_velocity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_ERROR_VELOCITY,
                                                    error_bt_velocity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM1_CORRELATION,
                                                    beam1_bt_correlation, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM2_CORRELATION,
                                                    beam2_bt_correlation, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM3_CORRELATION,
                                                    beam3_bt_correlation, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM4_CORRELATION,
                                                    beam4_bt_correlation, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM1_EVAL_AMP,
                                                    beam1_eval_amp, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM2_EVAL_AMP,
                                                    beam2_eval_amp, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM3_EVAL_AMP,
                                                    beam3_eval_amp, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM4_EVAL_AMP,
                                                    beam4_eval_amp, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM1_PERCENT_GOOD,
                                                    beam1_bt_percent_good, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM2_PERCENT_GOOD,
                                                    beam2_bt_percent_good, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM3_PERCENT_GOOD,
                                                    beam3_bt_percent_good, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM4_PERCENT_GOOD,
                                                    beam4_bt_percent_good, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_REF_LAYER_MIN,
                                                    ref_layer_min, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_REF_LAYER_NEAR,
                                                    ref_layer_near, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_REF_LAYER_FAR,
                                                    ref_layer_far, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_EASTWARD_REF_LAYER_VELOCITY,
                                                    beam1_ref_layer_velocity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_NORTHWARD_REF_LAYER_VELOCITY,
                                                    beam2_ref_layer_velocity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_UPWARD_REF_LAYER_VELOCITY,
                                                    beam3_ref_layer_velocity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_ERROR_REF_LAYER_VELOCITY,
                                                    beam4_ref_layer_velocity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM1_REF_CORRELATION,
                                                    beam1_ref_correlation, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM2_REF_CORRELATION,
                                                    beam2_ref_correlation, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM3_REF_CORRELATION,
                                                    beam3_ref_correlation, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM4_REF_CORRELATION,
                                                    beam4_ref_correlation, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM1_REF_INTENSITY,
                                                    beam1_ref_intensity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM2_REF_INTENSITY,
                                                    beam2_ref_intensity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM3_REF_INTENSITY,
                                                    beam3_ref_intensity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM4_REF_INTENSITY,
                                                    beam4_ref_intensity, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM1_REF_PERCENT_GOOD,
                                                    beam1_ref_percent_good, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM2_REF_PERCENT_GOOD,
                                                    beam2_ref_percent_good, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM3_REF_PERCENT_GOOD,
                                                    beam3_ref_percent_good, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM4_REF_PERCENT_GOOD,
                                                    beam4_ref_percent_good, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_MAX_DEPTH,
                                                    bt_max_depth, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM1_RSSI_AMPLITUDE,
                                                    beam1_rssi_amplitude, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM2_RSSI_AMPLITUDE,
                                                    beam2_rssi_amplitude, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM3_RSSI_AMPLITUDE,
                                                    beam3_rssi_amplitude, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_BEAM4_RSSI_AMPLITUDE,
                                                    beam4_rssi_amplitude, int))
        self.final_result.append(self._encode_value(AdcpPd0ParserDataParticleKey.BT_GAIN,
                                                    bt_gain, int))


class AdcpPd0Parser(BufferLoadingParser):
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        super(AdcpPd0Parser, self).__init__(config,
                                            stream_handle,
                                            state,
                                            self.sieve_function,
                                            state_callback,
                                            publish_callback,
                                            *args,
                                            **kwargs)

        self._read_state = {StateKey.POSITION: 0}

        if state:
            self.set_state(self._state)

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. 
        @throws DatasetParserException if there is a bad state structure
        """
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not ((StateKey.POSITION in state_obj)):
            raise DatasetParserException("Invalid state keys")

        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj
        self._chunker.clean_all_chunks()

        # seek to the position
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, increment):
        """
        Increment the parser state
        """
        self._read_state[StateKey.POSITION] += increment

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """
        result_particles = []
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
        self.handle_non_data(non_data, non_end, start)

        while chunk is not None:

            # particle-ize the data block received, return the record
            sample = self._extract_sample(self._particle_class, None, chunk, None)
            self._increment_state(len(chunk))
            if sample:
                # create particle
                log.trace("Extracting sample chunk %s with read_state: %s", chunk, self._read_state)
                result_particles.append((sample, copy.copy(self._read_state)))

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            self.handle_non_data(non_data, non_end, start)

        return result_particles

    def handle_non_data(self, non_data, non_end, start):
        """
        handle data in the non_data chunker queue
        @param non_data data in the non data chunker queue
        @param non_end ending index of the non_data chunk
        @param start start index of the next data chunk
        """
        # we can get non_data after our current chunk, check that this chunk is before that chunk
        if non_data is not None and non_end <= start:
            log.error("Found %d bytes of unexpected non-data:%s", len(non_data), non_data)
            self._exception_callback(UnexpectedDataException("Found %d bytes of un-expected non-data:%s" %
                                                             (len(non_data), non_data)))
            self._increment_state(len(non_data))

    def sieve_function(self, input_buffer):
        """
        Sort through the input buffer looking for a data record.
        A data record is considered to be properly framed if there is a
        sync word and the checksum matches.
        Arguments:
          input_buffer - the contents of the input stream
        Returns:
          A list of start,end tuples
        """

        #log.debug("sieve called with buffer of length %d", len(input_buffer))

        indices_list = []  # initialize the return list to empty
        header_iter = ADCPS_PD0_HEADER_MATCHER.finditer(input_buffer[0: -CHECKSUM_BYTES])
        #find all occurrences of the record header sentinel
        #don't look in the last 2 bytes because you will not have num bytes

        for match in header_iter:

            record_start = match.start()
            #place in string where sentinel was found

            #log.debug("sieve function found sentinel at byte  %d", record_start)

            num_bytes = struct.unpack("<H", input_buffer[record_start + 2: record_start + 4])[0]
            # get the number of bytes in the record, does not include the 2 checksum bytes

            record_end = record_start + num_bytes

            #log.debug("sieve function number of bytes= %d , record end is %d", num_bytes, record_end)

            #if there is enough in the buffer check the record
            if record_end <= len(input_buffer[0: -CHECKSUM_BYTES]):
                #make sure the checksum bytes are in the buffer too

                total = 0
                for i in range(record_start, record_end):
                    total += ord(input_buffer[i])
                #add up all the bytes in the record

                checksum = total & CHECKSUM_MODULO  # bitwise and with 65535 or mod vs 65536

                #log.debug("sieve checksum & total = %d %d ", checksum, total)

                if checksum == struct.unpack("<H", input_buffer[record_end: record_end + CHECKSUM_BYTES])[0]:
                    #verify the checksum
                    indices_list.append((record_start, record_end + CHECKSUM_BYTES))
                    #include the 2 checksum bytes in the chunk

                    #log.debug("sieve function found record.  Start = %d End = %d", record_start, record_end)

        return indices_list















