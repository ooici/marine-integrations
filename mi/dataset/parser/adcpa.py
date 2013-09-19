"""
@package mi.dataset.parser.adcpa
@file marine-integrations/mi/dataset/parser/adcpa.py
@author Christopher Wingard, using Teledyne ADCP instrument particles developed
    by Roger Unwin.
@brief Dataset code for the Coastal Slocum Adcpa mounted Teledyne ExplorerDVL
    (ADCPA) particles

Release notes:
    There are small differences between the PD0 formatted data files for the
    Teledyne RDI Workhorse series of ADCPs and the ExplorerDVL. The set of
    particles defined herein, will only work with the ExplorerDVL data files
    downloaded from TWR Coastal Slocum Adcpa. If the planned for AUVs also use
    the RDI ExplorerDVL, then these particles should apply to that instrument
    as well.

    Note, all binary data produced by the ExplorerDVL (and all other Teledyne
    RDI ADCPs) is little-endian.
"""
__author__ = 'Christopher Wingard'
__license__ = 'Apache 2.0'

import re
from struct import unpack
from calendar import timegm
import datetime as dt

from mi.core.log import get_logger
from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, DatasetParserException
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.dataset.dataset_parser import BufferLoadingParser

# start the logger
log = get_logger()

# Regex set to find the start of PD0 packet (first 6 bytes of the header data).
# This is more explicit than just the 0x7f7f marker the manual specifies. Using
# this regex helps avoid cases where the marker could actually be in the data
# string, thus giving a false positive data record marker.
ADCPA_PD0_PARSED_REGEX = b'(\x7f\x7f)([\x00-\xFF]{2})(\x00)(\x06|\x07)'
ADCPA_PD0_PARSED_REGEX_MATCHER = re.compile(ADCPA_PD0_PARSED_REGEX, re.DOTALL)


###############################################################################
# Data Particles
###############################################################################
class StateKey(BaseEnum):
    POSITION = "position"


class DataParticleType(BaseEnum):
    CGLDR_ADCPA_PD0_PARSED = 'cgldr_adcpa_pd0_parsed'


class ADCPA_PD0_PARSED_KEY(BaseEnum):
    """
    Data particles for the Teledyne RDI ExplorerDVL PD0 formatted data files
    """
    # Header Data
    HEADER_ID = 'header_id'
    DATA_SOURCE_ID = 'data_source_id'
    NUM_BYTES = 'num_bytes'
    NUM_DATA_TYPES = 'num_data_types'
    OFFSET_DATA_TYPES = 'offset_data_types'

    # Fixed Leader Data
    FIXED_LEADER_ID = 'fixed_leader_id'
    FIRMWARE_VERSION = 'firmware_version'
    FIRMWARE_REVISION = 'firmware_revision'
    SYSCONFIG_FREQUENCY = 'sysconfig_frequency'
    SYSCONFIG_BEAM_PATTERN = 'sysconfig_beam_pattern'
    SYSCONFIG_SENSOR_CONFIG = 'sysconfig_sensor_config'
    SYSCONFIG_HEAD_ATTACHED = 'sysconfig_head_attached'
    SYSCONFIG_VERTICAL_ORIENTATION = 'sysconfig_vertical_orientation'
    DATA_FLAG = 'data_flag'
    LAG_LENGTH = 'lag_length'
    NUM_BEAMS = 'num_beams'
    NUM_CELLS = 'num_cells'
    PINGS_PER_ENSEMBLE = 'pings_per_ensemble'
    DEPTH_CELL_LENGTH = 'depth_cell_length'
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
    SYSTEM_BANDWIDTH = 'system_bandwidth'
    SERIAL_NUMBER = 'serial_number'

    # Variable Leader Data
    VARIABLE_LEADER_ID = 'variable_leader_id'
    ENSEMBLE_NUMBER = 'ensemble_number'
    ENSEMBLE_NUMBER_INCREMENT = 'ensemble_number_increment'
    REAL_TIME_CLOCK = 'real_time_clock'
    ENSEMBLE_START_TIME = 'ensemble_start_time'
    BIT_RESULT_DEMOD_1 = 'bit_result_demod_1'
    BIT_RESULT_DEMOD_2 = 'bit_result_demod_2'
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

    # Velocity Data
    VELOCITY_DATA_ID = 'velocity_data_id'
    WATER_VELOCITY_EAST = 'water_velocity_east'
    WATER_VELOCITY_NORTH = 'water_velocity_north'
    WATER_VELOCITY_UP = 'water_velocity_up'
    ERROR_VELOCITY = 'error_velocity'

    # Correlation Magnitude Data
    CORRELATION_MAGNITUDE_ID = 'correlation_magnitude_id'
    CORRELATION_MAGNITUDE_BEAM1 = 'correlation_magnitude_beam1'
    CORRELATION_MAGNITUDE_BEAM2 = 'correlation_magnitude_beam2'
    CORRELATION_MAGNITUDE_BEAM3 = 'correlation_magnitude_beam3'
    CORRELATION_MAGNITUDE_BEAM4 = 'correlation_magnitude_beam4'

    # Echo Intensity Data
    ECHO_INTENSITY_ID = 'echo_intensity_id'
    ECHO_INTENSITY_BEAM1 = 'echo_intensity_beam1'
    ECHO_INTENSITY_BEAM2 = 'echo_intensity_beam2'
    ECHO_INTENSITY_BEAM3 = 'echo_intensity_beam3'
    ECHO_INTENSITY_BEAM4 = 'echo_intensity_beam4'

    # Percent Good Data
    PERCENT_GOOD_ID = 'percent_good_id'
    PERCENT_GOOD_3BEAM = 'percent_good_3beam'
    PERCENT_TRANSFORMS_REJECT = 'percent_transforms_reject'
    PERCENT_BAD_BEAMS = 'percent_bad_beams'
    PERCENT_GOOD_4BEAM = 'percent_good_4beam'

    # Bottom Track Data (only produced if Adcpa is in less than 65 m of water)
    BOTTOM_TRACK_ID = 'bottom_track_id'
    BT_PINGS_PER_ENSEMBLE = 'bt_pings_per_ensemble'
    BT_DELAY_BEFORE_REACQUIRE = 'bt_delay_before_reacquire'
    BT_CORR_MAGNITUDE_MIN = 'bt_corr_magnitude_min'
    BT_EVAL_MAGNITUDE_MIN = 'bt_eval_magnitude_min'
    BT_PERCENT_GOOD_MIN = 'bt_percent_good_min'
    BT_MODE = 'bt_mode'
    BT_ERROR_VELOCITY_MAX = 'bt_error_velocity_max'
    BEAM1_BT_RANGE_LSB = 'beam1_bt_range_lsb'
    BEAM2_BT_RANGE_LSB = 'beam2_bt_range_lsb'
    BEAM3_BT_RANGE_LSB = 'beam3_bt_range_lsb'
    BEAM4_BT_RANGE_LSB = 'beam4_bt_range_lsb'
    EASTWARD_BT_VELOCITY = 'eastward_bt_velocity'
    NORTHWARD_BT_VELOCITY = 'northward_bt_velocity'
    UPWARD_BT_VELOCITY = 'upward_bt_velocity'
    ERROR_BT_VELOCITY = 'error_bt_velocity'
    BEAM1_BT_CORRELATION = 'beam1_bt_correlation'
    BEAM2_BT_CORRELATION = 'beam2_bt_correlation'
    BEAM3_BT_CORRELATION = 'beam3_bt_correlation'
    BEAM4_BT_CORRELATION = 'beam4_bt_correlation'
    BEAM1_EVAL_AMP = 'beam1_eval_amp'
    BEAM2_EVAL_AMP = 'beam2_eval_amp'
    BEAM3_EVAL_AMP = 'beam3_eval_amp'
    BEAM4_EVAL_AMP = 'beam4_eval_amp'
    BEAM1_BT_PERCENT_GOOD = 'beam1_bt_percent_good'
    BEAM2_BT_PERCENT_GOOD = 'beam2_bt_percent_good'
    BEAM3_BT_PERCENT_GOOD = 'beam3_bt_percent_good'
    BEAM4_BT_PERCENT_GOOD = 'beam4_bt_percent_good'
    REF_LAYER_MIN = 'ref_layer_min'
    REF_LAYER_NEAR = 'ref_layer_near'
    REF_LAYER_FAR = 'ref_layer_far'
    BEAM1_REF_LAYER_VELOCITY = 'beam1_ref_layer_velocity'
    BEAM2_REF_LAYER_VELOCITY = 'beam2_ref_layer_velocity'
    BEAM3_REF_LAYER_VELOCITY = 'beam3_ref_layer_velocity'
    BEAM4_REF_LAYER_VELOCITY = 'beam4_ref_layer_velocity'
    BEAM1_REF_CORRELATION = 'beam1_ref_correlation'
    BEAM2_REF_CORRELATION = 'beam2_ref_correlation'
    BEAM3_REF_CORRELATION = 'beam3_ref_correlation'
    BEAM4_REF_CORRELATION = 'beam4_ref_correlation'
    BEAM1_REF_INTENSITY = 'beam1_ref_intensity'
    BEAM2_REF_INTENSITY = 'beam2_ref_intensity'
    BEAM3_REF_INTENSITY = 'beam3_ref_intensity'
    BEAM4_REF_INTENSITY = 'beam4_ref_intensity'
    BEAM1_REF_PERCENT_GOOD = 'beam1_ref_percent_good'
    BEAM2_REF_PERCENT_GOOD = 'beam2_ref_percent_good'
    BEAM3_REF_PERCENT_GOOD = 'beam3_ref_percent_good'
    BEAM4_REF_PERCENT_GOOD = 'beam4_ref_percent_good'
    BT_MAX_DEPTH = 'bt_max_depth'
    BEAM1_RSSI_AMPLITUDE = 'beam1_rssi_amplitude'
    BEAM2_RSSI_AMPLITUDE = 'beam2_rssi_amplitude'
    BEAM3_RSSI_AMPLITUDE = 'beam3_rssi_amplitude'
    BEAM4_RSSI_AMPLITUDE = 'beam4_rssi_amplitude'
    BT_GAIN = 'bt_gain'
    BEAM1_BT_RANGE_MSB = 'beam1_bt_range_msb'
    BEAM2_BT_RANGE_MSB = 'beam2_bt_range_msb'
    BEAM3_BT_RANGE_MSB = 'beam3_bt_range_msb'
    BEAM4_BT_RANGE_MSB = 'beam4_bt_range_msb'

    # Ensemble checksum
    CHECKSUM = 'checksum'


class ADCPA_PD0_PARSED_DataParticle(DataParticle):
    _data_particle_type = DataParticleType.CGLDR_ADCPA_PD0_PARSED

    def _build_parsed_values(self):
        """
        Parse the beginning portion of the ensemble (Header Data)
        """
        self.final_result = []

        length = unpack("<H", self.raw_data[2:4])[0]
        data = str(self.raw_data)

        # Calculate the checksum
        total = int(0)
        for i in range(0, length):
            total += int(ord(data[i]))

        checksum = total & 65535    # bitwise and with 65535 or mod vs 65536

        if checksum != unpack("<H", self.raw_data[length: length+2])[0]:
            log.debug("Checksum mismatch " + str(checksum) + " != "
                      + str(unpack("<H", self.raw_data[length: length+2])[0]))
            raise SampleException("Checksum mismatch")

        # save the checksum and process the remainder of the ensemble
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.CHECKSUM,
                                  DataParticleKey.VALUE: checksum})

        (header_id, data_source_id, num_bytes, spare, num_data_types) = \
            unpack('<BBHBB', self.raw_data[0:6])

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.HEADER_ID,
                                  DataParticleKey.VALUE: header_id})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.DATA_SOURCE_ID,
                                  DataParticleKey.VALUE: data_source_id})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.NUM_BYTES,
                                  DataParticleKey.VALUE: num_bytes})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.NUM_DATA_TYPES,
                                  DataParticleKey.VALUE: num_data_types})

        offsets = []    # create list for offsets
        strt = 6        # offsets start at byte 6 (using 0 indexing)
        nDT = 1         # counter for n data types
        while nDT <= num_data_types:
            value = unpack('<H', self.raw_data[strt:strt+2])[0]
            offsets.append(value)
            strt += 2
            nDT += 1

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.OFFSET_DATA_TYPES,
                                  DataParticleKey.VALUE: offsets})

        for offset in offsets:
            # for each offset, using the starting byte, determine the data type
            # and then parse accordingly.
            data_type = unpack('<H', self.raw_data[offset:offset+2])[0]

            # fixed leader data (x00x00)
            if data_type == 0:
                chunk = self.raw_data[offset:offset+58]
                self.parse_fixed_chunk(chunk)
                iCells = self.num_depth_cells   # grab the # of depth cells
                                                # obtained from the fixed leader
                                                # data type

            # variable leader data (x80x00)
            if data_type == 128:
                chunk = self.raw_data[offset:offset+60]
                self.parse_variable_chunk(chunk)

            # velocity data (x00x01)
            if data_type == 256:
                # number of bytes is a function of the user selectable number of
                # depth cells (WN command), calculated above
                nBytes = 2 + 8 * iCells
                chunk = self.raw_data[offset:offset+nBytes]
                self.parse_velocity_chunk(chunk)

            # correlation magnitude data (x00x02)
            if data_type == 512:
                # number of bytes is a function of the user selectable number of
                # depth cells (WN command), calculated above
                nBytes = 2 + 4 * iCells
                chunk = self.raw_data[offset:offset+nBytes]
                self.parse_corelation_magnitude_chunk(chunk)

            # echo intensity data (x00x03)
            if data_type == 768:
                # number of bytes is a function of the user selectable number of
                # depth cells (WN command), calculated above
                nBytes = 2 + 4 * iCells
                chunk = self.raw_data[offset:offset+nBytes]
                self.parse_echo_intensity_chunk(chunk)

            # percent-good data (x00x04)
            if data_type == 1024:
                # number of bytes is a function of the user selectable number of
                # depth cells (WN command), calculated above
                nBytes = 2 + 4 * iCells
                chunk = self.raw_data[offset:offset+nBytes]
                self.parse_percent_good_chunk(chunk)

            # bottom track data (x00x06)
            if data_type == 1536:
                chunk = self.raw_data[offset:offset+81]
                self.parse_bottom_track_chunk(chunk)

        return self.final_result

    def parse_fixed_chunk(self, chunk):
        """
        Parse the fixed leader portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        (fixed_leader_id, firmware_version, firmware_revision,
         sysconfig_frequency, data_flag, lag_length, num_beams, num_cells,
         pings_per_ensemble, depth_cell_length, blank_after_transmit,
         signal_processing_mode, low_corr_threshold, num_code_repetitions,
         percent_good_min, error_vel_threshold, time_per_ping_minutes,
         time_per_ping_seconds, time_per_ping_hundredths, coord_transform_type,
         heading_alignment, heading_bias, sensor_source, sensor_available,
         bin_1_distance, transmit_pulse_length, reference_layer_start,
         reference_layer_stop, false_target_threshold, SPARE1,
         transmit_lag_distance, SPARE2, system_bandwidth,
         SPARE3, SPARE4, serial_number) = \
            unpack('<HBBHBBBBHHHBBBBHBBBBhhBBHHBBBBHQHBBI', chunk)

        if 0 != fixed_leader_id:
            raise SampleException("fixed_leader_id was not equal to 0")

        # store the number of depth cells for use elsewhere
        self.num_depth_cells = num_cells

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.FIXED_LEADER_ID,
                                  DataParticleKey.VALUE: fixed_leader_id})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.FIRMWARE_VERSION,
                                  DataParticleKey.VALUE: firmware_version})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.FIRMWARE_REVISION,
                                  DataParticleKey.VALUE: firmware_revision})

        frequencies = [75, 150, 300, 600, 1200, 2400]

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SYSCONFIG_FREQUENCY,
                                  DataParticleKey.VALUE: frequencies[sysconfig_frequency & 0b00000111]})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SYSCONFIG_BEAM_PATTERN,
                                  DataParticleKey.VALUE: 1 if sysconfig_frequency & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SYSCONFIG_SENSOR_CONFIG,
                                  DataParticleKey.VALUE: sysconfig_frequency & 0b00110000 >> 4})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SYSCONFIG_HEAD_ATTACHED,
                                  DataParticleKey.VALUE: 1 if sysconfig_frequency & 0b01000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SYSCONFIG_VERTICAL_ORIENTATION,
                                  DataParticleKey.VALUE: 1 if sysconfig_frequency & 0b10000000 else 0})

        if 0 != data_flag:
            raise SampleException("data_flag was not equal to 0")

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.DATA_FLAG,
                                  DataParticleKey.VALUE: data_flag})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.LAG_LENGTH,
                                  DataParticleKey.VALUE: lag_length})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.NUM_BEAMS,
                                  DataParticleKey.VALUE: num_beams})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.NUM_CELLS,
                                  DataParticleKey.VALUE: num_cells})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.PINGS_PER_ENSEMBLE,
                                  DataParticleKey.VALUE: pings_per_ensemble})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.DEPTH_CELL_LENGTH,
                                  DataParticleKey.VALUE: depth_cell_length})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BLANK_AFTER_TRANSMIT,
                                  DataParticleKey.VALUE: blank_after_transmit})

        if 1 != signal_processing_mode:
            raise SampleException("signal_processing_mode was not equal to 1")

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SIGNAL_PROCESSING_MODE,
                                  DataParticleKey.VALUE: signal_processing_mode})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.LOW_CORR_THRESHOLD,
                                  DataParticleKey.VALUE: low_corr_threshold})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.NUM_CODE_REPETITIONS,
                                  DataParticleKey.VALUE: num_code_repetitions})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.PERCENT_GOOD_MIN,
                                  DataParticleKey.VALUE: percent_good_min})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ERROR_VEL_THRESHOLD,
                                  DataParticleKey.VALUE: error_vel_threshold})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.TIME_PER_PING_MINUTES,
                                  DataParticleKey.VALUE: time_per_ping_minutes})

        tpp_float_seconds = float(time_per_ping_seconds + (time_per_ping_hundredths/100))
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.TIME_PER_PING_SECONDS,
                                  DataParticleKey.VALUE: tpp_float_seconds})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.COORD_TRANSFORM_TYPE,
                                  DataParticleKey.VALUE: coord_transform_type & 0b00011000 >> 3})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.COORD_TRANSFORM_TILTS,
                                  DataParticleKey.VALUE: 1 if coord_transform_type & 0b00000100 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.COORD_TRANSFORM_BEAMS,
                                  DataParticleKey.VALUE: 1 if coord_transform_type & 0b0000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.COORD_TRANSFORM_MAPPING,
                                  DataParticleKey.VALUE: 1 if coord_transform_type & 0b00000001 else 0})

        # lame, but expedient - mask off un-needed bits
        self.coord_transform_type = (coord_transform_type & 0b00011000) >> 3

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.HEADING_ALIGNMENT,
                                  DataParticleKey.VALUE: heading_alignment})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.HEADING_BIAS,
                                  DataParticleKey.VALUE: heading_bias})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_SOURCE_SPEED,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b01000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_SOURCE_DEPTH,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b00100000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_SOURCE_HEADING,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b00010000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_SOURCE_PITCH,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_SOURCE_ROLL,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b00000100 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_SOURCE_CONDUCTIVITY,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b00000010 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_SOURCE_TEMPERATURE,
                                  DataParticleKey.VALUE: 1 if sensor_source & 0b00000001 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_AVAILABLE_DEPTH,
                                  DataParticleKey.VALUE: 1 if sensor_available & 0b00100000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_AVAILABLE_HEADING,
                                  DataParticleKey.VALUE: 1 if sensor_available & 0b00010000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_AVAILABLE_PITCH,
                                  DataParticleKey.VALUE: 1 if sensor_available & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_AVAILABLE_ROLL,
                                  DataParticleKey.VALUE: 1 if sensor_available & 0b00000100 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_AVAILABLE_CONDUCTIVITY,
                                  DataParticleKey.VALUE: 1 if sensor_available & 0b00000010 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SENSOR_AVAILABLE_TEMPERATURE,
                                  DataParticleKey.VALUE: 1 if sensor_available & 0b00000001 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BIN_1_DISTANCE,
                                  DataParticleKey.VALUE: bin_1_distance})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.TRANSMIT_PULSE_LENGTH,
                                  DataParticleKey.VALUE: transmit_pulse_length})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.REFERENCE_LAYER_START,
                                  DataParticleKey.VALUE: reference_layer_start})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.REFERENCE_LAYER_STOP,
                                  DataParticleKey.VALUE: reference_layer_stop})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.FALSE_TARGET_THRESHOLD,
                                  DataParticleKey.VALUE: false_target_threshold})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.TRANSMIT_LAG_DISTANCE,
                                  DataParticleKey.VALUE: transmit_lag_distance})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SYSTEM_BANDWIDTH,
                                  DataParticleKey.VALUE: system_bandwidth})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SERIAL_NUMBER,
                                  DataParticleKey.VALUE: serial_number})

    def parse_variable_chunk(self, chunk):
        """
        Parse the variable leader portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        rtc = {}
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
            unpack('<HHBBBBBBBBBBHHHhhHhBBBBBBBBBBBBBBBBBBHIII', chunk)

        if 128 != variable_leader_id:
            raise SampleException("variable_leader_id was not equal to 128")

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.VARIABLE_LEADER_ID,
                                  DataParticleKey.VALUE: variable_leader_id})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ENSEMBLE_NUMBER,
                                  DataParticleKey.VALUE: ensemble_number})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ENSEMBLE_NUMBER_INCREMENT,
                                  DataParticleKey.VALUE: ensemble_number_increment})

        # convert individual date and time values to datetime object and
        # calculate the NTP timestamp (seconds since Jan 1, 1900), per OOI
        # convention
        dts = dt.datetime(2000 + rtc['year'], rtc['month'], rtc['day'],
                          rtc['hour'], rtc['minute'], rtc['second'])
        epoch_ts = timegm(dts.timetuple()) + (rtc['hundredths'] / 100.0)  # seconds since 1970-01-01 in UTC
        ntp_ts = epts + 2208988800
        self.set_internal_timestamp(ntp_ts)

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.REAL_TIME_CLOCK,
                                 DataParticleKey.VALUE: [rtc['year'], rtc['month'], rtc['day'],
                                                         rtc['hour'], rtc['minute'], rtc['second'], rtc['hundredths']]})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ENSEMBLE_START_TIME,
                                 DataParticleKey.VALUE: epoch_ts})

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BIT_RESULT_DEMOD_1,
                                  DataParticleKey.VALUE: 1 if error_bit_field & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BIT_RESULT_DEMOD_2,
                                  DataParticleKey.VALUE: 1 if error_bit_field & 0b00010000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BIT_RESULT_TIMING,
                                  DataParticleKey.VALUE: 1 if error_bit_field & 0b00000010 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SPEED_OF_SOUND,
                                  DataParticleKey.VALUE: speed_of_sound})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.TRANSDUCER_DEPTH,
                                  DataParticleKey.VALUE: transducer_depth})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.HEADING,
                                  DataParticleKey.VALUE: heading})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.PITCH,
                                  DataParticleKey.VALUE: pitch})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ROLL,
                                  DataParticleKey.VALUE: roll})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SALINITY,
                                  DataParticleKey.VALUE: salinity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.TEMPERATURE,
                                  DataParticleKey.VALUE: temperature})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.MPT_MINUTES,
                                  DataParticleKey.VALUE: mpt_minutes})

        mpt_seconds = float(mpt_seconds_component + (mpt_hundredths_component/100))
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.MPT_SECONDS,
                                  DataParticleKey.VALUE: mpt_seconds})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.HEADING_STDEV,
                                  DataParticleKey.VALUE: heading_stdev})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.PITCH_STDEV,
                                  DataParticleKey.VALUE: pitch_stdev})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ROLL_STDEV,
                                  DataParticleKey.VALUE: roll_stdev})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ADC_TRANSMIT_CURRENT,
                                  DataParticleKey.VALUE: adc_transmit_current})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ADC_TRANSMIT_VOLTAGE,
                                  DataParticleKey.VALUE: adc_transmit_voltage})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ADC_AMBIENT_TEMP,
                                  DataParticleKey.VALUE: adc_ambient_temp})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ADC_PRESSURE_PLUS,
                                  DataParticleKey.VALUE: adc_pressure_plus})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ADC_PRESSURE_MINUS,
                                  DataParticleKey.VALUE: adc_pressure_minus})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ADC_ATTITUDE_TEMP,
                                  DataParticleKey.VALUE: adc_attitude_temp})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ADC_ATTITUDE,
                                  DataParticleKey.VALUE: adc_attitiude})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ADC_CONTAMINATION_SENSOR,
                                  DataParticleKey.VALUE: adc_contamination_sensor})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BUS_ERROR_EXCEPTION,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00000001 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ADDRESS_ERROR_EXCEPTION,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00000010 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ILLEGAL_INSTRUCTION_EXCEPTION,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00000100 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ZERO_DIVIDE_INSTRUCTION,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.EMULATOR_EXCEPTION,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00010000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.UNASSIGNED_EXCEPTION,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00100000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.WATCHDOG_RESTART_OCCURRED,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b01000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BATTERY_SAVER_POWER,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b10000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.PINGING,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b00000001 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.COLD_WAKEUP_OCCURRED,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b01000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.UNKNOWN_WAKEUP_OCCURRED,
                                  DataParticleKey.VALUE: 1 if error_status_word_1 & 0b10000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.CLOCK_READ_ERROR,
                                  DataParticleKey.VALUE: 1 if error_status_word_3 & 0b00000001 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.UNEXPECTED_ALARM,
                                  DataParticleKey.VALUE: 1 if error_status_word_3 & 0b00000010 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.CLOCK_JUMP_FORWARD,
                                  DataParticleKey.VALUE: 1 if error_status_word_3 & 0b00000100 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.CLOCK_JUMP_BACKWARD,
                                  DataParticleKey.VALUE: 1 if error_status_word_3 & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.POWER_FAIL,
                                  DataParticleKey.VALUE: 1 if error_status_word_4 & 0b00001000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SPURIOUS_DSP_INTERRUPT,
                                  DataParticleKey.VALUE: 1 if error_status_word_4 & 0b00010000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SPURIOUS_UART_INTERRUPT,
                                  DataParticleKey.VALUE: 1 if error_status_word_4 & 0b00100000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.SPURIOUS_CLOCK_INTERRUPT,
                                  DataParticleKey.VALUE: 1 if error_status_word_4 & 0b01000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.LEVEL_7_INTERRUPT,
                                  DataParticleKey.VALUE: 1 if error_status_word_4 & 0b10000000 else 0})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.PRESSURE,
                                  DataParticleKey.VALUE: pressure})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.PRESSURE_VARIANCE,
                                  DataParticleKey.VALUE: pressure_variance})

    def parse_velocity_chunk(self, chunk):
        """
        Parse the velocity portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        N = (len(chunk) - 2) / 2 / 4
        offset = 0

        velocity_data_id = unpack("<H", chunk[0:2])[0]
        if 256 != velocity_data_id:
            raise SampleException("velocity_data_id was not equal to 256")

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.VELOCITY_DATA_ID,
                                  DataParticleKey.VALUE: velocity_data_id})

        water_velocity_east = []
        water_velocity_north = []
        water_velocity_up = []
        error_velocity = []
        for row in range(1, N):
            (a, b, c, d) = unpack('<hhhh', chunk[offset + 2: offset + 10])
            water_velocity_east.append(a)
            water_velocity_north.append(b)
            water_velocity_up.append(c)
            error_velocity.append(d)
            offset += 4 * 2
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.WATER_VELOCITY_EAST,
                                  DataParticleKey.VALUE: water_velocity_east})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.WATER_VELOCITY_NORTH,
                                  DataParticleKey.VALUE: water_velocity_north})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.WATER_VELOCITY_UP,
                                  DataParticleKey.VALUE: water_velocity_up})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ERROR_VELOCITY,
                                  DataParticleKey.VALUE: error_velocity})

    def parse_corelation_magnitude_chunk(self, chunk):
        """
        Parse the corelation magnitude portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        N = (len(chunk) - 2) / 4
        offset = 0

        correlation_magnitude_id = unpack("<H", chunk[0:2])[0]
        if 512 != correlation_magnitude_id:
            raise SampleException("correlation_magnitude_id was not equal to 512")

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_ID,
                                  DataParticleKey.VALUE: correlation_magnitude_id})

        correlation_magnitude_beam1 = []
        correlation_magnitude_beam2 = []
        correlation_magnitude_beam3 = []
        correlation_magnitude_beam4 = []
        for row in range(1, N):
            (a, b, c, d) = unpack('<BBBB', chunk[offset + 2: offset + 6])
            correlation_magnitude_beam1.append(a)
            correlation_magnitude_beam2.append(b)
            correlation_magnitude_beam3.append(c)
            correlation_magnitude_beam4.append(d)
            offset += 4

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM1,
                                  DataParticleKey.VALUE: correlation_magnitude_beam1})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM2,
                                  DataParticleKey.VALUE: correlation_magnitude_beam2})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM3,
                                  DataParticleKey.VALUE: correlation_magnitude_beam3})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM4,
                                  DataParticleKey.VALUE: correlation_magnitude_beam4})

    def parse_echo_intensity_chunk(self, chunk):
        """
        Parse the echo intensity portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        N = (len(chunk) - 2) / 4
        offset = 0

        echo_intensity_id = unpack("<H", chunk[0:2])[0]
        if 768 != echo_intensity_id:
            raise SampleException("echo_intensity_id was not equal to 768")
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ECHO_INTENSITY_ID,
                                  DataParticleKey.VALUE: echo_intensity_id})

        echo_intesity_beam1 = []
        echo_intesity_beam2 = []
        echo_intesity_beam3 = []
        echo_intesity_beam4 = []
        for row in range(1, N):
            (a, b, c, d) = unpack('<BBBB', chunk[offset + 2: offset + 6])
            echo_intesity_beam1.append(a)
            echo_intesity_beam2.append(b)
            echo_intesity_beam3.append(c)
            echo_intesity_beam4.append(d)
            offset += 4

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM1,
                                  DataParticleKey.VALUE: echo_intesity_beam1})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM2,
                                  DataParticleKey.VALUE: echo_intesity_beam2})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM3,
                                  DataParticleKey.VALUE: echo_intesity_beam3})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM4,
                                  DataParticleKey.VALUE: echo_intesity_beam4})

    def parse_percent_good_chunk(self, chunk):
        """
        Parse the percent good portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        N = (len(chunk) - 2) / 4
        offset = 0

        percent_good_id = unpack("<H", chunk[0:2])[0]
        if 1024 != percent_good_id:
            raise SampleException("percent_good_id was not equal to 1024")

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.PERCENT_GOOD_ID,
                                  DataParticleKey.VALUE: percent_good_id})

        percent_good_3beam = []
        percent_transforms_reject = []
        percent_bad_beams = []
        percent_good_4beam = []
        for row in range(1, N):
            (a, b, c, d) = unpack('<BBBB', chunk[offset + 2: offset + 6])
            percent_good_3beam.append(a)
            percent_transforms_reject.append(b)
            percent_bad_beams.append(c)
            percent_good_4beam.append(d)
            offset += 4
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.PERCENT_GOOD_3BEAM,
                                  DataParticleKey.VALUE: percent_good_3beam})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.PERCENT_TRANSFORMS_REJECT,
                                  DataParticleKey.VALUE: percent_transforms_reject})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.PERCENT_BAD_BEAMS,
                                  DataParticleKey.VALUE: percent_bad_beams})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.PERCENT_GOOD_4BEAM,
                                  DataParticleKey.VALUE: percent_good_4beam})

    def parse_bottom_track_chunk(self, chunk):
        """
        Parse the bottom track portion of the particle

        @throws SampleException If there is a problem with sample creation
        """
        (bottom_track_id, bt_pings_per_ensemble, bt_delay_before_reacquire,
         bt_corr_magnitude_min, bt_eval_magnitude_min, bt_percent_good_min,
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
            unpack('<HHHBBBBHLHHHHhhhhBBBBBBBBBBBBHHHhhhhBBBBBBBBBBBBHBBBBBBBBB', chunk)

        if 1536 != bottom_track_id:
            raise SampleException("bottom_track_id was not equal to 1536")

        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BOTTOM_TRACK_ID,
                                  DataParticleKey.VALUE: bottom_track_id})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BT_PINGS_PER_ENSEMBLE,
                                  DataParticleKey.VALUE: bt_pings_per_ensemble})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BT_DELAY_BEFORE_REACQUIRE,
                                  DataParticleKey.VALUE: bt_delay_before_reacquire})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BT_CORR_MAGNITUDE_MIN,
                                  DataParticleKey.VALUE: bt_corr_magnitude_min})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BT_EVAL_MAGNITUDE_MIN,
                                  DataParticleKey.VALUE: bt_eval_magnitude_min})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BT_PERCENT_GOOD_MIN,
                                  DataParticleKey.VALUE: bt_percent_good_min})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BT_MODE,
                                  DataParticleKey.VALUE: bt_mode})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BT_ERROR_VELOCITY_MAX,
                                  DataParticleKey.VALUE: bt_error_velocity_max})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM1_BT_RANGE_LSB,
                                  DataParticleKey.VALUE: beam1_bt_range_lsb})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM2_BT_RANGE_LSB,
                                  DataParticleKey.VALUE: beam2_bt_range_lsb})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM3_BT_RANGE_LSB,
                                  DataParticleKey.VALUE: beam3_bt_range_lsb})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM4_BT_RANGE_LSB,
                                  DataParticleKey.VALUE: beam4_bt_range_lsb})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.EASTWARD_BT_VELOCITY,
                                  DataParticleKey.VALUE: eastward_bt_velocity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.NORTHWARD_BT_VELOCITY,
                                  DataParticleKey.VALUE: northward_bt_velocity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.UPWARD_BT_VELOCITY,
                                  DataParticleKey.VALUE: upward_bt_velocity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.ERROR_BT_VELOCITY,
                                  DataParticleKey.VALUE: error_bt_velocity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM1_BT_CORRELATION,
                                  DataParticleKey.VALUE: beam1_bt_correlation})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM2_BT_CORRELATION,
                                  DataParticleKey.VALUE: beam2_bt_correlation})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM3_BT_CORRELATION,
                                  DataParticleKey.VALUE: beam3_bt_correlation})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM4_BT_CORRELATION,
                                  DataParticleKey.VALUE: beam4_bt_correlation})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM1_EVAL_AMP,
                                  DataParticleKey.VALUE: beam1_eval_amp})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM2_EVAL_AMP,
                                  DataParticleKey.VALUE: beam2_eval_amp})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM3_EVAL_AMP,
                                  DataParticleKey.VALUE: beam3_eval_amp})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM4_EVAL_AMP,
                                  DataParticleKey.VALUE: beam4_eval_amp})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM1_BT_PERCENT_GOOD,
                                  DataParticleKey.VALUE: beam1_bt_percent_good})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM2_BT_PERCENT_GOOD,
                                  DataParticleKey.VALUE: beam2_bt_percent_good})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM3_BT_PERCENT_GOOD,
                                  DataParticleKey.VALUE: beam3_bt_percent_good})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM4_BT_PERCENT_GOOD,
                                  DataParticleKey.VALUE: beam4_bt_percent_good})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.REF_LAYER_MIN,
                                  DataParticleKey.VALUE: ref_layer_min})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.REF_LAYER_NEAR,
                                  DataParticleKey.VALUE: ref_layer_near})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.REF_LAYER_FAR,
                                  DataParticleKey.VALUE: ref_layer_far})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM1_REF_LAYER_VELOCITY,
                                  DataParticleKey.VALUE: beam1_ref_layer_velocity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM2_REF_LAYER_VELOCITY,
                                  DataParticleKey.VALUE: beam2_ref_layer_velocity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM3_REF_LAYER_VELOCITY,
                                  DataParticleKey.VALUE: beam3_ref_layer_velocity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM4_REF_LAYER_VELOCITY,
                                  DataParticleKey.VALUE: beam4_ref_layer_velocity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM1_REF_CORRELATION,
                                  DataParticleKey.VALUE: beam1_ref_correlation})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM2_REF_CORRELATION,
                                  DataParticleKey.VALUE: beam2_ref_correlation})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM3_REF_CORRELATION,
                                  DataParticleKey.VALUE: beam3_ref_correlation})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM4_REF_CORRELATION,
                                  DataParticleKey.VALUE: beam4_ref_correlation})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM1_REF_INTENSITY,
                                  DataParticleKey.VALUE: beam1_ref_intensity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM2_REF_INTENSITY,
                                  DataParticleKey.VALUE: beam2_ref_intensity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM3_REF_INTENSITY,
                                  DataParticleKey.VALUE: beam3_ref_intensity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM4_REF_INTENSITY,
                                  DataParticleKey.VALUE: beam4_ref_intensity})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM1_REF_PERCENT_GOOD,
                                  DataParticleKey.VALUE: beam1_ref_percent_good})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM2_REF_PERCENT_GOOD,
                                  DataParticleKey.VALUE: beam2_ref_percent_good})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM3_REF_PERCENT_GOOD,
                                  DataParticleKey.VALUE: beam3_ref_percent_good})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM4_REF_PERCENT_GOOD,
                                  DataParticleKey.VALUE: beam4_ref_percent_good})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BT_MAX_DEPTH,
                                  DataParticleKey.VALUE: bt_max_depth})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM1_RSSI_AMPLITUDE,
                                  DataParticleKey.VALUE: beam1_rssi_amplitude})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM2_RSSI_AMPLITUDE,
                                  DataParticleKey.VALUE: beam2_rssi_amplitude})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM3_RSSI_AMPLITUDE,
                                  DataParticleKey.VALUE: beam3_rssi_amplitude})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM4_RSSI_AMPLITUDE,
                                  DataParticleKey.VALUE: beam4_rssi_amplitude})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BT_GAIN,
                                  DataParticleKey.VALUE: bt_gain})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM1_BT_RANGE_MSB,
                                  DataParticleKey.VALUE: beam1_bt_range_msb})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM2_BT_RANGE_MSB,
                                  DataParticleKey.VALUE: beam2_bt_range_msb})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM3_BT_RANGE_MSB,
                                  DataParticleKey.VALUE: beam3_bt_range_msb})
        self.final_result.append({DataParticleKey.VALUE_ID: ADCPA_PD0_PARSED_KEY.BEAM4_BT_RANGE_MSB,
                                  DataParticleKey.VALUE: beam4_bt_range_msb})


class AdcpaParser(BufferLoadingParser):
    """
    AdcpaParser parses a TRDI ExplorerDVL (ADCPA) PD0 formatted data file that
    has been logged on the TWR Slocum Coastal Electric Glider.
    """
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        super(AdcpaParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          state_callback,
                                          publish_callback,
                                          *args,
                                          **kwargs)
        self._record_buffer = []  # holds tuples of (record, state)
        self._read_state = {StateKey.POSITION: 0}
        if state:
            self.set_state(self._state)

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. Should be a dict with
            a StateKey.POSITION value. The position is the number of bytes into
            the file.
        @throws DatasetParserException if there is a bad state structure
        """
        log.trace("Attempting to set state to: %s", state_obj)
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not StateKey.POSITION in state_obj:
            raise DatasetParserException("Invalid state keys")

        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        # seek to it
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, increment):
        """
        Increment the parser position by a certain amount in bytes. This
        indicates what has been READ from the file, not what has been published.

        This is a base implementation, override as needed.

        @param increment Number of bytes to increment the parser position.
        """
        log.trace("Incrementing current state: %s with increment: %s",
                  self._read_state, increment)

        self._read_state[StateKey.POSITION] += increment

    def parse_chunks(self):
        """
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list is returned if nothing was
            parsed.
        """
        # read in the pd0 data file and find the indexes to the record markers
        data = self._stream_handle.read()
        n = [m.span() for m in re.finditer(ADCPA_PD0_PARSED_REGEX_MATCHER, data)]

        result_particles = []
        # now parse the file, ensemble by ensemble, publishing the results as we go.
        for i in range(0, len(n)):
            # start at the first ensemble header
            strt = n[i][0]

            # use information in the ensemble to get the number of bytes --
            # this is variable depending on the presence or absence of the
            # bottom tracking data. Also, pilots may change the ExplorerDVL
            # settings mid-deployment in order to conserve battery life or for
            # other reasons. Allowing the ensemble to self define, means the
            # code should be robust in the face of such changes.
            numBytes = unpack("<H", data[strt+2:strt+4])[0]
            end = strt + numBytes + 2
            ensemble = data[strt:end]

            # create a new regex for this ensemble given the full number of
            # bytes (number of bytes + 2 byte checksum) with the number of
            # header bytes in the earlier regex string removed.
            plusBytes = (numBytes + 2) - 6
            ensemble_regex = re.compile((ADCPA_PD0_PARSED_REGEX + '([\x00-\xFF]{%s})'.format(plusBytes+2)), re.DOTALL)

            # particleize the data block received and return the record -- the
            # internal time stamp is set in the DataParticle.
            sample = self._extract_sample(self._particle_class, ensemble_regex, ensemble, None)

            if sample:
                # valid sample received, create the particle
                self._increment_state(numBytes + 2)
                result_particles.append((sample, copy.copy(self._read_state)))

        # save the results
        return result_particles
