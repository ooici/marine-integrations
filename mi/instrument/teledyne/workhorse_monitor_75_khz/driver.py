"""
@package mi.instrument.teledyne.workhorse_monitor_75_khz.cgsn.driver
@file marine-integrations/mi/instrument/teledyne/workhorse_monitor_75_khz/cgsn/driver.py
@author Lytle Johnson
@brief Driver for the cgsn
Release notes:

moving to teledyne
"""

__author__ = 'Lytle Johnson'
__license__ = 'Apache 2.0'

import re
import time as time
import string
import ntplib
import datetime as dt

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum


from mi.instrument.teledyne.driver import ADCPInstrumentDriver
from mi.instrument.teledyne.driver import ADCPProtocol
#from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver


from mi.core.instrument.instrument_fsm import InstrumentFSM

from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentStateException
from struct import *

# newline.
NEWLINE = '\n'

# default timeout.
TIMEOUT = 10

BYTE_SIZE = 2  # number of chars per byte
WORD_SIZE = 4  # number of chars per 2-byte word

#data ensemble invariant indices
NUM_BYTES_IN_ENSEMBLE_INDEX = 4
NUM_DATA_TYPES_INDEX = 10
DATA_TYPE_LOC_INDEX_BASE = 12

#
# Particle Regex's'
#
# TODO: add the regex to make this work
ADCP_PD0_PARSED_REGEX = r'7F7F'
ADCP_PD0_PARSED_REGEX_MATCHER = re.compile(ADCP_PD0_PARSED_REGEX)

# TODO: add the regex to make this work
ADCP_SYSTEM_CONFIGURATION_REGEX = r''
ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER = re.compile(ADCP_SYSTEM_CONFIGURATION_REGEX)


ADCP_COMPASS_CALIBRATION_REGEX = r'(ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM.*)>'
ADCP_COMPASS_CALIBRATION_REGEX_MATCHER = re.compile(ADCP_COMPASS_CALIBRATION_REGEX)

"""
ENSEMBLE_HEADER_ID = '7F7F'
FIXED_LEADER_ID = '0000'
VAR_LEADER_ID = '8000'
VELOCITY_ID = '0001'
CORR_MAG_ID = '0002'
ECHO_INTENSITY_ID = '0003'
PERCENT_GOOD_ID = '0004'
STATUS_ID = '0005'
BOTTOM_TRACK_ID = '0006'
ENSEMBLE_LENGTH_LOC = 4  # index in header where number of bytes in ensemble is located

## globals
NumCells = 0  # value from fixed leader datq; used to determine size of velocity and other data records.
num_data_types = 0  # value from header data; used to determine size of header record and total number of data records.
num_bytes_in_ensemble = 0  # value from header data; used to determine size of ensemble and calculate checksum.
"""

class InstrumentCmds(BaseEnum):
    """
    Device specific commands
    Represents the commands the driver implements and the string that
    must be sent to the instrument to execute the command.
    """
    EXPERT_ON = 'EXPERTON'
    EXPERT_OFF = 'EXPERTOFF'

    BREAK = 'break 500'
    SEND_LAST_DATA_ENSEMBLE = 'CE'
    SAVE_SETUP_TO_RAM = 'CK'
    START_DEPLOYMENT = 'CS'
    OUTPUT_CALIBRATION_DATA = 'AC'
    CLEAR_ERROR_STATUS_WORD = 'CY0'         # May combine with next
    DISPLAY_ERROR_STATUS_WORD = 'CY1'       # May combine with prior
    CLEAR_FAULT_LOG = 'FC'
    DISPLAY_FAULT_LOG = 'FD'
    GET_SYSTEM_CONFIGURATION = 'PS0'
    GET_INSTRUMENT_TRANSFORM_MATRIX = 'PS3'
    RUN_TEST_200 = 'PT200'

    SET = ' '  # leading spaces are OK. set is just PARAM_NAME next to VALUE
    GET = '  '


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    #TEST = DriverProtocolState.TEST
    #POLL = DriverProtocolState.POLL


class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """

    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT

    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS  # DOES IT HAVE THIS?
    ACQUIRE_CONFIGURATION = "PROTOCOL_EVENT_ACQUIRE_CONFIGURATION"  # DOES IT HAVE THIS?
    SEND_LAST_SAMPLE = "PROTOCOL_EVENT_SEND_LAST_SAMPLE"

    GET = DriverEvent.GET
    SET = DriverEvent.SET

    DISCOVER = DriverEvent.DISCOVER

    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT

    PING_DRIVER = DriverEvent.PING_DRIVER

    CLOCK_SYNC = DriverEvent.CLOCK_SYNC

    # Different event because we don't want to expose this as a capability
    SCHEDULED_CLOCK_SYNC = 'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC'

    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE         # DOES IT HAVE THIS?
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE

    QUIT_SESSION = 'PROTOCOL_EVENT_QUIT_SESSION'


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
    ACQUIRE_CONFIGURATION = ProtocolEvent.ACQUIRE_CONFIGURATION
    SEND_LAST_SAMPLE = ProtocolEvent.SEND_LAST_SAMPLE
    QUIT_SESSION = ProtocolEvent.QUIT_SESSION
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC


class Parameter(DriverParameter):
    """
    Device parameters
    """
    #
    # set-able parameters
    #
    SERIAL_DATA_OUT = 'CD'              # 000 000 000 Serial Data Out (Vel;Cor;Amp PG;St;P0 P1;P2;P3)
    SERIAL_FLOW_CONTROL = 'CF'          # 11110  Flow Ctrl (EnsCyc;PngCyc;Binry;Ser;Rec)
    BANNER = 'CH'                       # Suppress Banner 0=Show, 1=Suppress
    INSTRUMENT_ID = 'CI'                # Int 0-255
    SLEEP_ENABLE = 'CL'                 # 0/1
    SAVE_NVRAM_TO_RECORDER = 'CN'       # Save NVRAM to recorder (0 = ON, 1 = OFF)
    POLLED_MODE = 'CP'                  # 1=ON, 0=OFF;
    XMIT_POWER = 'CQ'                   # 0=Low, 255=High

    SPEED_OF_SOUND = 'EC'               # 1500  Speed Of Sound (m/s)
    PITCH = 'EP'                        # Tilt 1 Sensor (1/100 deg) -6000 to 6000 (-60.00 to +60.00 degrees)
    ROLL = 'ER'                         # Tilt 2 Sensor (1/100 deg) -6000 to 6000 (-60.00 to +60.00 degrees)
    SALINITY = 'ES'                     # 35 (0-40 pp thousand)
    SENSOR_SOURCE = 'EZ'                # Sensor Source (C;D;H;P;R;S;T)

    TIME_PER_ENSEMBLE = 'TE'            # 01:00:00.00 (hrs:min:sec.sec/100)
    TIME_OF_FIRST_PING = 'TG'           # ****/**/**,**:**:** (CCYY/MM/DD,hh:mm:ss)
    TIME_PER_PING = 'TP'                # 00:00.20  (min:sec.sec/100)
    TIME = 'TT'                         # 2013/02/26,05:28:23 (CCYY/MM/DD,hh:mm:ss)

    FALSE_TARGET_THRESHOLD = 'WA'       # 255,001 (Max)(0-255),Start Bin # <--------- TRICKY.... COMPLEX TYPE
    BANDWIDTH_CONTROL = 'WB'            # Bandwidth Control (0=Wid,1=Nar)
    CORRELATION_THRESHOLD = 'WC'        # 064  Correlation Threshold
    SERIAL_OUT_FW_SWITCHES = 'WD'       # 111100000  Data Out (Vel;Cor;Amp PG;St;P0 P1;P2;P3)
    ERROR_VELOCITY_THRESHOLD = 'WE'     # 5000  Error Velocity Threshold (0-5000 mm/s)
    BLANK_AFTER_TRANSMIT = 'WF'         # 0088  Blank After Transmit (cm)
    CLIP_DATA_PAST_BOTTOM = 'WI'        # 0 Clip Data Past Bottom (0=OFF,1=ON)
    RECEIVER_GAIN_SELECT = 'WJ'         # 1  Rcvr Gain Select (0=Low,1=High)
    WATER_REFERENCE_LAYER = 'WL'        # 001,005  Water Reference Layer: Begin Cell (0=OFF), End Cell
    WATER_PROFILING_MODE = 'WM'         # Profiling Mode (1-15)
    NUMBER_OF_DEPTH_CELLS = 'WN'        # Number of depth cells (1-255)
    PINGS_PER_ENSEMBLE = 'WP'           # Pings per Ensemble (0-16384)
    DEPTH_CELL_SIZE = 'WS'              # 0800  Depth Cell Size (cm)
    TRANSMIT_LENGTH = 'WT'              # 0000 Transmit Length 0 to 3200(cm) 0 = Bin Length
    PING_WEIGHT = 'WU'                  # 0 Ping Weighting (0=Box,1=Triangle)
    AMBIGUITY_VELOCITY = 'WV'           # 175 Mode 1 Ambiguity Vel (cm/s radial)
    PINGS_BEFORE_REAQUIRE = 'WW'        # Mode 1 Pings before Mode 4 Re-acquire


class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """
    COMMAND = '>'
    AUTOSAMPLE = ''
    ERR = 'ERR:'


class ScheduledJob(BaseEnum):
    """
    Complete this last.
    """
    #ACQUIRE_STATUS = 'acquire_status'
    #CALIBRATION_COEFFICIENTS = 'calibration_coefficients'
    #CLOCK_SYNC = 'clock_sync'


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
    PART_000_uint8 = "header_id"
    PART_001_uint8 = "data_source_id"
    PART_002_uint16 = "num_bytes"
    PART_003_uint16 = "num_data_types"
    PART_004_uint16 = "offset_data_types"
    PART_005_uint16 = "fixed_leader_id"
    PART_006_uint8 = "firmware_version"
    PART_007_uint8 = "firmware_revision"
    PART_008_uint16 = "sysconfig_frequency"
    PART_009_int8 = "sysconfig_beam_pattern"
    PART_010_uint8 = "sysconfig_sensor_config"
    PART_011_int8 = "sysconfig_head_attached"
    PART_012_int8 = "sysconfig_vertical_orientation"
    PART_013_uint8 = "data_flag"
    PART_014_uint8 = "lag_length"
    PART_015_uint8 = "num_beams"
    PART_016_uint8 = "num_cells"
    PART_017_uint16 = "pings_per_ensemble"
    PART_018_uint16 = "depth_cell_length"
    PART_019_uint16 = "blank_after_transmit"
    PART_020_uint8 = "signal_processing_mode"
    PART_021_uint8 = "low_corr_threshold"
    PART_022_uint8 = "num_code_repetitions"
    PART_023_uint8 = "percent_good_min"
    PART_024_uint16 = "error_vel_threshold"
    PART_025_uint8 = "time_per_ping_minutes"
    PART_026_float32 = "time_per_ping_seconds"
    PART_027_uint8 = "coord_transform_type"
    PART_028_int8 = "coord_transform_tilts"
    PART_029_int8 = "coord_transform_beams"
    PART_030_int8 = "coord_transform_mapping"
    PART_031_int16 = "heading_alignment"
    PART_032_int16 = "heading_bias"
    PART_033_int8 = "sensor_source_speed"
    PART_034_int8 = "sensor_source_depth"
    PART_035_int8 = "sensor_source_heading"
    PART_036_int8 = "sensor_source_pitch"
    PART_037_int8 = "sensor_source_roll"
    PART_038_int8 = "sensor_source_conductivity"
    PART_039_int8 = "sensor_source_temperature"
    PART_040_int8 = "sensor_available_depth"
    PART_041_int8 = "sensor_available_heading"
    PART_042_int8 = "sensor_available_pitch"
    PART_043_int8 = "sensor_available_roll"
    PART_044_int8 = "sensor_available_conductivity"
    PART_045_int8 = "sensor_available_temperature"
    PART_046_uint16 = "bin_1_distance"
    PART_047_uint16 = "transmit_pulse_length"
    PART_048_uint16 = "reference_layer_start"
    PART_049_uint16 = "reference_layer_stop"
    PART_050_uint16 = "false_target_threshold"
    PART_051_int8 = "low_latency_trigger"
    PART_052_uint16 = "transmit_lag_distance"
    PART_053_uint64 = "cpu_board_serial_number"
    PART_054_uint8 = "system_bandwidth"
    PART_055_uint8 = "system_power"
    PART_056_uint32 = "serial_number"
    PART_057_uint8 = "beam_angle"
    PART_058_uint16 = "variable_leader_id"
    PART_059_uint16 = "ensemble_number"
    PART_060_float64 = "internal_timestamp"
    PART_061_uint8 = "ensemble_number_increment"
    PART_062_int8 = "bit_result_demod_1"
    PART_063_int8 = "bit_result_demod_2"
    PART_064_int8 = "bit_result_timing"
    PART_065_uint16 = "speed_of_sound"
    PART_066_uint16 = "transducer_depth"
    PART_067_uint16 = "heading"
    PART_068_int16 = "pitch"
    PART_069_int16 = "roll"
    PART_070_uint16 = "salinity"
    PART_071_int16 = "temperature"
    PART_072_uint8 = "mpt_minutes"
    PART_073_float32 = "mpt_seconds"
    PART_074_uint8 = "heading_stdev"
    PART_075_uint8 = "pitch_stdev"
    PART_076_uint8 = "roll_stdev"
    PART_077_uint8 = "adc_transmit_current"
    PART_078_uint8 = "adc_transmit_voltage"
    PART_079_uint8 = "adc_ambient_temp"
    PART_080_uint8 = "adc_pressure_plus"
    PART_081_uint8 = "adc_pressure_minus"
    PART_082_uint8 = "adc_attitude_temp"
    PART_083_uint8 = "adc_attitiude"
    PART_084_uint8 = "adc_contamination_sensor"
    PART_085_uint8 = "bus_error_exception"
    PART_086_uint8 = "address_error_exception"
    PART_087_uint8 = "illegal_instruction_exception"
    PART_088_uint8 = "zero_divide_instruction"
    PART_089_uint8 = "emulator_exception"
    PART_090_uint8 = "unassigned_exception"
    PART_091_uint8 = "watchdog_restart_occurred"
    PART_092_uint8 = "battery_saver_power"
    PART_093_uint8 = "pinging"
    PART_094_uint8 = "cold_wakeup_occurred"
    PART_095_uint8 = "unknown_wakeup_occurred"
    PART_096_uint8 = "clock_read_error"
    PART_097_uint8 = "unexpected_alarm"
    PART_098_uint8 = "clock_jump_forward"
    PART_099_uint8 = "clock_jump_backward"
    PART_100_uint8 = "power_fail"
    PART_101_uint8 = "spurious_dsp_interrupt"
    PART_102_uint8 = "spurious_uart_interrupt"
    PART_103_uint8 = "spurious_clock_interrupt"
    PART_104_uint8 = "level_7_interrupt"
    PART_105_uint32 = "absolute_pressure"
    PART_106_uint32 = "pressure_variance"
    PART_107_float64 = "internal_timestamp"
    PART_108_uint16 = "velocity_data_id"
    PART_109_int16 = "water_velocity_east"
    PART_110_int16 = "water_velocity_north"
    PART_111_int16 = "water_velocity_up"
    PART_112_int16 = "error_velocity"
    PART_113_uint16 = "correlation_magnitude_id"
    PART_114_uint8 = "correlation_magnitude_beam1"
    PART_115_uint8 = "correlation_magnitude_beam2"
    PART_116_uint8 = "correlation_magnitude_beam3"
    PART_117_uint8 = "correlation_magnitude_beam4"
    PART_118_uint16 = "echo_intensity_id"
    PART_119_uint8 = "echo_intesity_beam1"
    PART_120_uint8 = "echo_intesity_beam2"
    PART_121_uint8 = "echo_intesity_beam3"
    PART_122_uint8 = "echo_intesity_beam4"
    PART_123_uint16 = "percent_good_id"
    PART_124_uint8 = "percent_good_3beam"
    PART_125_uint8 = "percent_transforms_reject"
    PART_126_uint8 = "percent_bad_beams"
    PART_127_uint8 = "percent_good_4beam"
    PART_128_uint16 = "checksum"


class ADCP_PD0_PARSED_DataParticle(DataParticle):
    _data_particle_type = DataParticleType.ADCP_PD0_PARSED

    def _build_parsed_values(self):

        data_stream = self.raw_data
        # uint8 = B
        # int8 = b
        # uint16 = H
        # int16 = h
        # int32 = l
        # uint32 = L
        # float32 = f
        # float64 = d
        result = {}
        result[ADCP_PD0_PARSED_KEY.PART_000_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_001_uint8], 
        result[ADCP_PD0_PARSED_KEY.PART_002_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_003_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_004_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_005_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_006_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_007_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_008_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_009_int8],
        result[ADCP_PD0_PARSED_KEY.PART_010_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_011_int8],
        result[ADCP_PD0_PARSED_KEY.PART_012_int8],
        result[ADCP_PD0_PARSED_KEY.PART_013_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_014_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_015_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_016_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_017_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_018_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_019_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_020_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_021_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_022_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_023_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_024_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_025_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_026_float32],
        result[ADCP_PD0_PARSED_KEY.PART_027_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_028_int8],
        result[ADCP_PD0_PARSED_KEY.PART_029_int8],
        result[ADCP_PD0_PARSED_KEY.PART_030_int8],
        result[ADCP_PD0_PARSED_KEY.PART_031_int16],
        result[ADCP_PD0_PARSED_KEY.PART_032_int16],
        result[ADCP_PD0_PARSED_KEY.PART_033_int8],
        result[ADCP_PD0_PARSED_KEY.PART_034_int8],
        result[ADCP_PD0_PARSED_KEY.PART_035_int8],
        result[ADCP_PD0_PARSED_KEY.PART_036_int8],
        result[ADCP_PD0_PARSED_KEY.PART_037_int8],
        result[ADCP_PD0_PARSED_KEY.PART_038_int8],
        result[ADCP_PD0_PARSED_KEY.PART_039_int8],
        result[ADCP_PD0_PARSED_KEY.PART_040_int8],
        result[ADCP_PD0_PARSED_KEY.PART_041_int8],
        result[ADCP_PD0_PARSED_KEY.PART_042_int8],
        result[ADCP_PD0_PARSED_KEY.PART_043_int8],
        result[ADCP_PD0_PARSED_KEY.PART_044_int8],
        result[ADCP_PD0_PARSED_KEY.PART_045_int8],
        result[ADCP_PD0_PARSED_KEY.PART_046_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_047_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_048_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_049_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_050_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_051_int8],
        result[ADCP_PD0_PARSED_KEY.PART_052_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_053_uint64],
        result[ADCP_PD0_PARSED_KEY.PART_054_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_055_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_056_uint32],
        result[ADCP_PD0_PARSED_KEY.PART_057_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_058_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_059_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_060_float64],
        result[ADCP_PD0_PARSED_KEY.PART_061_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_062_int8],
        result[ADCP_PD0_PARSED_KEY.PART_063_int8],
        result[ADCP_PD0_PARSED_KEY.PART_064_int8],
        result[ADCP_PD0_PARSED_KEY.PART_065_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_066_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_067_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_068_int16],
        result[ADCP_PD0_PARSED_KEY.PART_069_int16],
        result[ADCP_PD0_PARSED_KEY.PART_070_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_071_int16],
        result[ADCP_PD0_PARSED_KEY.PART_072_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_073_float32],
        result[ADCP_PD0_PARSED_KEY.PART_074_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_075_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_076_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_077_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_078_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_079_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_080_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_081_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_082_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_083_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_084_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_085_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_086_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_087_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_088_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_089_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_090_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_091_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_092_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_093_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_094_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_095_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_096_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_097_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_098_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_099_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_100_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_101_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_102_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_103_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_104_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_105_uint32],
        result[ADCP_PD0_PARSED_KEY.PART_106_uint32],
        result[ADCP_PD0_PARSED_KEY.PART_107_float64],
        result[ADCP_PD0_PARSED_KEY.PART_108_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_109_int16],
        result[ADCP_PD0_PARSED_KEY.PART_110_int16],
        result[ADCP_PD0_PARSED_KEY.PART_111_int16],
        result[ADCP_PD0_PARSED_KEY.PART_112_int16],
        result[ADCP_PD0_PARSED_KEY.PART_113_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_114_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_115_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_116_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_117_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_118_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_119_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_120_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_121_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_122_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_123_uint16],
        result[ADCP_PD0_PARSED_KEY.PART_124_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_125_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_126_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_127_uint8],
        result[ADCP_PD0_PARSED_KEY.PART_128_uint16] \
        = unpack('BBHHHHBBHbBbbBBBBHHHBBBBHBfBbbbh' + \
                 'hbbbbbbbbbbbbbHHHHHbHdBBLBHHdBbb' + \
                 'bHHHhhHhBfBBBBBBBBBBBBBBBBBBBBBB' + \
                 'BBBBBBBBBLLdHhhhhHBBBBHBBBBHBBBBH', data_stream)

        #
        # Left Off Here
        #

        if m is not None:
            # don't put the '>' in the data particle
            value = m.group()[:-1]
        else:
            value = None
        result = [{DataParticleKey.VALUE_ID: ADCPT_PT200DataParticleKey.PT200_DATA,
                   DataParticleKey.VALUE: value}]
        return result


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

    def _build_parsed_values(self):

        data_stream = self.raw_data
        m = re.search(PS0_REGEX, data_stream)
        if m is not None:
            # don't put the '>' in the data particle
            value = m.group()[:-1]
        else:
            value = None
        result = [{DataParticleKey.VALUE_ID: ADCPT_PS0DataParticleKey.PS0_DATA,
                   DataParticleKey.VALUE: value}]
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
    ROLL_UP_DOWN = "roll_up_down"
    PITCH_UP_DOWN = "pitch_up_down"
    OFFSET_UP_DOWN = "offset_up_down"
    TILT_NULL = "tilt_null"

"""
CALIBRATION_RAW_DATA = \
"" + NEWLINE +\
"              ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM" + NEWLINE + \
"               Calibration date and time: 9/14/2012  09:25:32" + NEWLINE + \
"                             S inverse" + NEWLINE + \
"          " + EF_CHAR + "                                                  " + EF_CHAR + "" + NEWLINE + \
"     Bx   " + EF_CHAR + "   3.9218e-01  3.9660e-01 -3.1681e-02  6.4332e-03 " + EF_CHAR + "" + NEWLINE + \
"     By   " + EF_CHAR + "  -2.4320e-02 -1.0376e-02 -2.2428e-03 -6.0628e-01 " + EF_CHAR + "" + NEWLINE + \
"     Bz   " + EF_CHAR + "   2.2453e-01 -2.1972e-01 -2.7990e-01 -2.4339e-03 " + EF_CHAR + "" + NEWLINE + \
"     Err  " + EF_CHAR + "   4.6514e-01 -4.0455e-01  6.9083e-01 -1.4291e-02 " + EF_CHAR + "" + NEWLINE + \
"          " + EF_CHAR + "                                                  " + EF_CHAR + "" + NEWLINE + \
"                             Coil Offset" + NEWLINE + \
"                         " + EF_CHAR + "                " + EF_CHAR + "" + NEWLINE + \
"                         " + EF_CHAR + "   3.4233e+04   " + EF_CHAR + "" + NEWLINE + \
"                         " + EF_CHAR + "   3.4449e+04   " + EF_CHAR + "" + NEWLINE + \
"                         " + EF_CHAR + "   3.4389e+04   " + EF_CHAR + "" + NEWLINE + \
"                         " + EF_CHAR + "   3.4698e+04   " + EF_CHAR + "" + NEWLINE + \
"                         " + EF_CHAR + "                " + EF_CHAR + "" + NEWLINE + \
"                             Electrical Null" + NEWLINE + \
"                              " + EF_CHAR + "       " + EF_CHAR + "" + NEWLINE + \
"                              " + EF_CHAR + " 34285 " + EF_CHAR + "" + NEWLINE + \
"                              " + EF_CHAR + "       " + EF_CHAR + "" + NEWLINE + \
"                    TILT CALIBRATION MATRICES in NVRAM" + NEWLINE + \
"                Calibration date and time: 9/14/2012  09:14:45" + NEWLINE + \
"              Average Temperature During Calibration was   24.4 " + EF_CHAR + "C" + NEWLINE + \
"" + NEWLINE + \
"                   Up                              Down" + NEWLINE + \
"" + NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + "" + NEWLINE + \
" Roll   " + EF_CHAR + "   7.4612e-07  -3.1727e-05 " + EF_CHAR + "     " + EF_CHAR + "  -3.0054e-07   3.2190e-05 " + EF_CHAR + "" + NEWLINE + \
" Pitch  " + EF_CHAR + "  -3.1639e-05  -6.3505e-07 " + EF_CHAR + "     " + EF_CHAR + "  -3.1965e-05  -1.4881e-07 " + EF_CHAR + "" + NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + "" + NEWLINE + \
"" + NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + "" + NEWLINE + \
" Offset " + EF_CHAR + "   3.2808e+04   3.2568e+04 " + EF_CHAR + "     " + EF_CHAR + "   3.2279e+04   3.3047e+04 " + EF_CHAR + "" + NEWLINE + \
"        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + "" + NEWLINE + \
"" + NEWLINE + \
"                             " + EF_CHAR + "       " + EF_CHAR + "" + NEWLINE + \
"                      Null   " + EF_CHAR + " 33500 " + EF_CHAR + "" + NEWLINE + \
"                             " + EF_CHAR + "       " + EF_CHAR + "" + NEWLINE + \
"" + NEWLINE + \
"" + NEWLINE + \
"" + NEWLINE + \
"" + NEWLINE + \
"" + NEWLINE + \
">"

"""


class ADCP_COMPASS_CALIBRATION_DataParticle(DataParticle):
    _data_particle_type = DataParticleType.ADCP_COMPASS_CALIBRATION

    def _build_parsed_values(self):

        data_stream = self.raw_data
        m = re.search(PS3_REGEX, data_stream)
        if m is not None:
            # don't put the '>' in the data particle
            value = m.group()[:-1]
        else:
            value = None
        result = [{DataParticleKey.VALUE_ID: ADCPT_PS3DataParticleKey.PS3_DATA,
                   DataParticleKey.VALUE: value}]
        return result


###############################################################################
# Driver
###############################################################################

class TeledyneInstrumentDriver(ADCPInstrumentDriver):
#class TeledyneInstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass for Workhorse 75khz driver.
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    def __init__(self, evt_callback):
        """
        InstrumentDriver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        ADCPInstrumentDriver.__init__(self, evt_callback)
        #SingleConnectionInstrumentDriver.__init__(self, evt_callback)

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
        #self._protocol = ADCPProtocol(Prompt, NEWLINE, self._driver_event)
        self._protocol = TeledyneProtocol(Prompt, NEWLINE, self._driver_event)

###########################################################################
# Protocol
###########################################################################

class TeledyneProtocol(ADCPProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """

        log.debug("IN TeledyneProtocol.__init__")
        # Construct protocol superclass.
        ADCPProtocol.__init__(self, prompts, newline, driver_event)

        # Build ADCPT protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)
        log.debug("ASSIGNED self._protocol_fsm")
        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN,
                                       ProtocolEvent.ENTER,
                                       self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN,
                                       ProtocolEvent.EXIT,
                                       self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN,
                                       ProtocolEvent.DISCOVER,
                                       self._handler_unknown_discover)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND,
                                       ProtocolEvent.ENTER,
                                       self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND,
                                       ProtocolEvent.EXIT,
                                       self._handler_command_exit)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND,
                                       ProtocolEvent.GET,
                                       self._handler_command_autosample_test_get)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND,
                                       ProtocolEvent.ACQUIRE_SAMPLE,
                                       self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND,
                                       ProtocolEvent.START_AUTOSAMPLE,
                                       self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND,
                                       ProtocolEvent.SET,
                                       self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND,
                                       ProtocolEvent.CLOCK_SYNC,
                                       self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND,
                                       ProtocolEvent.SCHEDULED_CLOCK_SYNC,
                                       self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND,
                                       ProtocolEvent.ACQUIRE_STATUS,
                                       self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND,
                                       ProtocolEvent.ACQUIRE_CONFIGURATION,
                                       self._handler_command_acquire_configuration)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND,
                                       ProtocolEvent.QUIT_SESSION,
                                       self._handler_command_quit_session)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND,
                                       ProtocolEvent.START_DIRECT,
                                       self._handler_command_start_direct)


        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE,
                                       ProtocolEvent.ENTER,
                                       self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE,
                                       ProtocolEvent.EXIT,
                                       self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE,
                                       ProtocolEvent.GET,
                                       self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE,
                                       ProtocolEvent.ACQUIRE_STATUS,
                                       self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE,
                                       ProtocolEvent.ACQUIRE_CONFIGURATION,
                                       self._handler_command_acquire_configuration)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE,
                                       ProtocolEvent.STOP_AUTOSAMPLE,
                                       self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE,
                                       ProtocolEvent.SEND_LAST_SAMPLE,
                                       self._handler_command_send_last_sample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE,
                                       ProtocolEvent.SCHEDULED_CLOCK_SYNC,
                                       self._handler_autosample_clock_sync)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS,
                                       ProtocolEvent.ENTER,
                                       self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS,
                                       ProtocolEvent.EXIT,
                                       self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS,
                                       ProtocolEvent.EXECUTE_DIRECT,
                                       self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS,
                                       ProtocolEvent.STOP_DIRECT,
                                       self._handler_direct_access_stop_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        #
        # These will need a handful of shared functions to stage the 
        # parameters to the commands
        #

        self._add_build_handler(InstrumentCmds.BREAK,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.EXPERT_ON,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.EXPERT_OFF,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.OUTPUT_CALIBRATION_DATA,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SEND_LAST_DATA_ENSEMBLE,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SAVE_SETUP_TO_RAM,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.START_DEPLOYMENT,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.CLEAR_ERROR_STATUS_WORD,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_ERROR_STATUS_WORD,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.CLEAR_FAULT_LOG,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_FAULT_LOG,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GET_SYSTEM_CONFIGURATION,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.RUN_TEST_200,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SET,
                                self._build_set_command)
        self._add_build_handler(InstrumentCmds.GET,
                                self._build_get_command)



        #
        # Response handlers
        #
        self._add_response_handler(InstrumentCmds.BREAK,
                                self._parse_break_response)
        self._add_response_handler(InstrumentCmds.EXPERT_ON,
                                self._parse_expert_on_response)
        self._add_response_handler(InstrumentCmds.EXPERT_OFF,
                                self._parse_expert_off_response)
        self._add_response_handler(InstrumentCmds.OUTPUT_CALIBRATION_DATA,
                                self._parse_output_calibration_data_response)
        self._add_response_handler(InstrumentCmds.SEND_LAST_DATA_ENSEMBLE,
                                self._parse_send_last_data_ensemble_response)
        self._add_response_handler(InstrumentCmds.SAVE_SETUP_TO_RAM,
                                self._parse_save_setup_to_ram_response)
        self._add_response_handler(InstrumentCmds.START_DEPLOYMENT,
                                self._parse_start_deployment_response)
        self._add_response_handler(InstrumentCmds.CLEAR_ERROR_STATUS_WORD,
                                self._parse_clear_error_status_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_ERROR_STATUS_WORD,
                                self._parse_error_status_response)
        self._add_response_handler(InstrumentCmds.CLEAR_FAULT_LOG,
                                self._parse_clear_fault_log_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_FAULT_LOG,
                                self._parse_fault_log_response)
        self._add_response_handler(InstrumentCmds.GET_SYSTEM_CONFIGURATION,
                                self._parse_system_configuration_response)
        self._add_response_handler(InstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX,
                                self._parse_instrument_transform_matrix_response)
        self._add_response_handler(InstrumentCmds.RUN_TEST_200,
                                self._parse_test_response)
        self._add_response_handler(InstrumentCmds.SET,
                                self._parse_set_response)
        self._add_response_handler(InstrumentCmds.GET,
                                self._parse_get_response)


        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be
        # filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(TeledyneProtocol.sieve_function)

        #self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS,
        #                          ProtocolEvent.ACQUIRE_STATUS)
        #self._add_scheduler_event(ScheduledJob.CALIBRATION_COEFFICIENTS,
        #                          ProtocolEvent.ACQUIRE_CONFIGURATION)
        #self._add_scheduler_event(ScheduledJob.CLOCK_SYNC,
        #                          ProtocolEvent.SCHEDULED_CLOCK_SYNC)

    def _build_simple_command(self, cmd):
        """
        Build handler for basic adcpt commands.
        @param cmd the simple adcpt command to format
                (no value to attach to the command)
        @retval The command to be sent to the device.
        """
        log.debug("build_simple_command: %s" % cmd)
        return cmd + NEWLINE

    def get_word_value(self, s, index):
        """
        Returns value of a 2-byte word in an
        ascii-hex string into a decimal integer
        """
        return int(s[index + 2:index + 4] + s[index: index + 2], 16)

    @staticmethod
    def sieve_function(raw_data):
        """
        Chunker sieve method to help the chunker identify chunks.
        @returns a list of chunks identified, if any.
        The chunks are all the same type.
        """

        sieve_matchers = [ADCP_PD0_PARSED_REGEX_MATCHER,
                          ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER,
                          ADCP_COMPASS_CALIBRATION_REGEX_MATCHER,]

        return_list = []

        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with sbe26plus parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """

        self._param_dict.add(Parameter.SERIAL_DATA_OUT,
            r'CD = (\d\d\d \d\d\d \d\d\d) \-+ Serial Data Out \(Vel;Cor;Amp  PG;St;P0  P1;P2;P3\)',
            lambda match: str(match.group(1)),
            self._string_to_string,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.SERIAL_FLOW_CONTROL,
            r'CF = (\d+) \-+ Flow Ctrl \(EnsCyc;PngCyc;Binry;Ser;Rec\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=11110)

        self._param_dict.add(Parameter.BANNER,
            r'CH = (\d) \-+ Suppress Banner',
            lambda match: not bool(int(match.group(1))),
            self._reverse_bool_to_int,
            startup_param=True,
            default_value=True)

        self._param_dict.add(Parameter.INSTRUMENT_ID,
            r'CI = (\d+) \-+ Instrument ID \(0-255\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True)

        self._param_dict.add(Parameter.SLEEP_ENABLE,
            r'CL = (\d) \-+ Sleep Enable',
            lambda match: bool(int(match.group(1))),
            self._bool_to_int,
            startup_param=True,
            default_value=False)

        self._param_dict.add(Parameter.SAVE_NVRAM_TO_RECORDER,
            r'CN = (\d) \-+ Save NVRAM to recorder',
            lambda match: bool(int(match.group(1))),
            self._bool_to_int,
            startup_param=True,
            default_value=True,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.POLLED_MODE,
            r'CP = (\d) \-+ PolledMode \(1=ON, 0=OFF;  BREAK resets\)',
            lambda match: bool(int(match.group(1))),
            self._bool_to_int,
            startup_param=True,
            default_value=False)

        self._param_dict.add(Parameter.XMIT_POWER,
            r'CQ = (\d+) \-+ Xmt Power \(0=Low, 255=High\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=255)

        self._param_dict.add(Parameter.SPEED_OF_SOUND,
            r'EC = (\d+) \-+ Speed Of Sound',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=1485)

        self._param_dict.add(Parameter.PITCH,
            r'EP = ([\+\-\d]+) \-+ Tilt 1 Sensor \(1/100 deg\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.ROLL,
            r'ER = ([\+\-\d]+) \-+ Tilt 2 Sensor \(1/100 deg\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.SALINITY,
            r'ES = (\d+) \-+ Salinity \(0-40 pp thousand\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=35)

        self._param_dict.add(Parameter.SENSOR_SOURCE,
            r'EZ = (\d+) \-+ Sensor Source \(C;D;H;P;R;S;T\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True)

        self._param_dict.add(Parameter.TIME_PER_ENSEMBLE,
            r'TE (\d\d:\d\d:\d\d.\d\d) \-+ Time per Ensemble \(hrs:min:sec.sec/100\)',
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True,
            default_value='00:00.00')

        self._param_dict.add(Parameter.TIME_OF_FIRST_PING,
            r'TG (..../../..,..:..:..) - Time of First Ping \(CCYY/MM/DD,hh:mm:ss\)',
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True)

        self._param_dict.add(Parameter.TIME_PER_PING,
            r'TP (\d\d:\d\d.\d\d) \-+ Time per Ping',
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True,
            default_value='00:01.00')

        self._param_dict.add(Parameter.TIME,
            r'TT (\d\d\d\d/\d\d/\d\d,\d\d:\d\d:\d\d) \- Time Set ',
            lambda match: str(match.group(1)), #time.strptime(match.group(1), "%Y/%m/%d,%H:%M:%S"),
            self._string_to_string,
            startup_param=True)

        self._param_dict.add(Parameter.FALSE_TARGET_THRESHOLD,
            r'WA (\d+,\d+) \-+ False Target Threshold \(Max\)\(0-255\),\[Start Bin\]',
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True,
            default_value='050,001')

        self._param_dict.add(Parameter.BANDWIDTH_CONTROL,
            r'WB (\d) \-+ Bandwidth Control \(0=Wid,1=Nar\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.CORRELATION_THRESHOLD,
            r'WC (\d+) \-+ Correlation Threshold',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=64)

        self._param_dict.add(Parameter.SERIAL_OUT_FW_SWITCHES,
            r'WD (\s+) \-+ Data Out \(Vel;Cor;Amp  PG;St;P0  P1;P2;P3\)',
            lambda match: str(match.group(1)),
            self._string_to_string,
            visibility=ParameterDictVisibility.READ_ONLY,
            startup_param=True,
            default_value='111 100 000')

        self._param_dict.add(Parameter.ERROR_VELOCITY_THRESHOLD,
            r'WE (\d+) \-+ Error Velocity Threshold',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=2000)

        self._param_dict.add(Parameter.BLANK_AFTER_TRANSMIT,
            r'WF (\d+) \-+ Blank After Transmit',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=704)

        self._param_dict.add(Parameter.CLIP_DATA_PAST_BOTTOM,
            r'WI (\d) \-+ Clip Data Past Bottom',
            lambda match: bool(int(match.group(1))),
            self._bool_to_int,
            startup_param=True,
            default_value=False)

        self._param_dict.add(Parameter.RECEIVER_GAIN_SELECT,
            r'WJ (\d) \-+ Rcvr Gain Select \(0=Low,1=High\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=1)

        self._param_dict.add(Parameter.WATER_REFERENCE_LAYER,
            r'WL (\d+,\d+) \-+ Water Reference Layer:  Begin Cell \(0=OFF\), End Cell',
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True,
            default_value='001,005')

        self._param_dict.add(Parameter.WATER_PROFILING_MODE,
            r'WM (\d+) \-+ Profiling Mode \(1\-15\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            visibility=ParameterDictVisibility.READ_ONLY,
            startup_param=True,
            default_value=1)

        self._param_dict.add(Parameter.NUMBER_OF_DEPTH_CELLS,
            r'WN (\d+) \-+ Number of depth cells',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=100)

        self._param_dict.add(Parameter.PINGS_PER_ENSEMBLE,
            r'WP (\d+) \-+ Pings per Ensemble ',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=1)

        self._param_dict.add(Parameter.DEPTH_CELL_SIZE,
            r'WS (\d+) \-+ Depth Cell Size \(cm\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=800)

        self._param_dict.add(Parameter.TRANSMIT_LENGTH,
            r'WT (\d+) \-+ Transmit Length \(cm\) \[0 = Bin Length\]',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.PING_WEIGHT,
            r'WU (\d) \-+ Ping Weighting \(0=Box,1=Triangle\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.AMBIGUITY_VELOCITY,
            r'WV (\d+) \-+ Mode 1 Ambiguity Vel \(cm/s radial\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            startup_param=True,
            default_value=175)


    ########################################################################
    # Startup parameter handlers
    ########################################################################
    def apply_startup_params(self):
        """
        Apply all startup parameters.  First we check the instrument to see
        if we need to set the parameters.  If they are they are set
        correctly then we don't do anything.

        If we need to set parameters then we might need to transition to
        command first.  Then we will transition back when complete.

        @todo: This feels odd.  It feels like some of this logic should
               be handled by the state machine.  It's a pattern that we
               may want to review.  I say this because this command
               needs to be run from autosample or command mode.
        @raise: InstrumentProtocolException if not in command or streaming
        """
        # Let's give it a try in unknown state
        log.debug("CURRENT STATE: %s" % self.get_current_state())
        if (self.get_current_state() != ProtocolState.COMMAND and
            self.get_current_state() != ProtocolState.AUTOSAMPLE):
            raise InstrumentProtocolException("Not in command or autosample state. Unable to apply startup params")

        logging = self._is_logging()

        # If we are in streaming mode and our configuration on the
        # instrument matches what we think it should be then we
        # don't need to do anything.
        if(not self._instrument_config_dirty()):
            return True

        error = None

        try:
            if(logging):
                # Switch to command mode,
                self._stop_logging()

            self._apply_params()

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            if(logging):
                self._start_logging()

        if(error):
            raise error

    def _instrument_config_dirty(self):
        """
        Read the startup config and compare that to what the instrument
        is configured too.  If they differ then return True
        @return: True if the startup config doesn't match the instrument
        @raise: InstrumentParameterException
        """
        # Refresh the param dict cache

        # Let's assume we have already run this command recently
        #self._do_cmd_resp(InstrumentCmds.DISPLAY_STATUS)
        self._do_cmd_resp(InstrumentCmds.DISPLAY_CALIBRATION)

        startup_params = self._param_dict.get_startup_list()
        log.debug("Startup Parameters: %s" % startup_params)

        for param in startup_params:
            if not Parameter.has(param):
                raise InstrumentParameterException()

            if (self._param_dict.get(param) != self._param_dict.get_config_value(param)):
                log.debug("DIRTY: %s %s != %s" % (param, self._param_dict.get(param), self._param_dict.get_config_value(param)))
                return True

        log.debug("Clean instrument config")
        return False

    ########################################################################
    # Private helpers.
    ########################################################################

    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the sbe26plus device.
        """
        self._connection.send(NEWLINE)

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Send a CE (send last data ensemble)
        command to the adcpt; this causes the chunker to extract last data
        and put in adcpt_cache_dict.  Then calling _build_param_dict() causes
        the new data to be updated in param dict.
        """
        # Get old param dict config.
        log.debug("IN _update_params" + str(args) + str(kwargs))
        old_config = self._param_dict.get_config()
        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        # Issue display commands and parse results.

        kwargs['expected_prompt'] = Prompt.COMMAND
        cmds = dir(Parameter)

        log.debug("CMDS = %s", str(cmds))
        for attr in cmds:
            log.debug("attr = %s",str(attr))
            if attr not in ['dict', 'has', 'list', 'ALL']:
                if not attr.startswith("_"):
                    key = getattr(Parameter, attr)
                    log.debug("YES!!!!! ######################### KEY = " + str(key))
                    result = self._do_cmd_resp(InstrumentCmds.GET, key, **kwargs)
                    log.debug("RESULT OF GET WAS %s", result)

        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.
        Pass it to extract_sample with the appropriate particle
        objects and REGEXes.
        """

        if (self._extract_sample(ADCP_PD0_PARSED_DataParticle,
                                 ADCP_PD0_PARSED_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("successful match for ADCP_PD0_PARSED_DataParticle")
            return

        if (self._extract_sample(ADCP_SYSTEM_CONFIGURATION_DataParticle,
                                 ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("successful match for ADCP_SYSTEM_CONFIGURATION_DataParticle")
            return

        if (self._extract_sample(ADCP_COMPASS_CALIBRATION_DataParticle,
                                 ADCP_COMPASS_CALIBRATION_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("successful match for ADCP_COMPASS_CALIBRATION_DataParticle")
            return

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    ########################################################################
    # response handlers.
    ########################################################################
    ### Not sure if these are needed, since I'm creating data particles
    ### for the information.

    def _parse_break_response(self, response, prompt):
        """
        """

    def _parse_zero_pressure_reading_response(self, response, prompt):
        """
        """

    def _parse_fault_debug_response(self, response, prompt):
        """
        """

    def _parse_expert_on_response(self, response, prompt):
        """
        """

    def _parse_expert_off_response(self, response, prompt):
        """
        """

    def _parse_list_firmware_upgrades_response(self, response, prompt):
        """
        """

    def _parse_output_calibration_data_response(self, response, prompt):
        """
        """

    def _parse_output_factory_calibration_data_response(self, response, prompt):
        """
        """

    def _parse_field_calibrate_compas_response(self, response, prompt):
        """
        """

    def _parse_load_factory_calibration_response(self, response, prompt):
        """
        """

    def _parse_choose_external_devices_response(self, response, prompt):
        """
        """

    def _parse_send_last_data_ensemble_response(self, response, prompt):
        """
        """

    def _parse_save_setup_to_ram_response(self, response, prompt):
        """
        """

    def _parse_retrieve_parameters_response(self, response, prompt):
        """
        """

    def _parse_start_deployment_response(self, response, prompt):
        """
        """

    def _parse_clear_error_status_response(self, response, prompt):
        """
        """

    def _parse_error_status_response(self, response, prompt):
        """
        """

    def _parse_power_down_response(self, response, prompt):
        """
        """

    def _parse_load_speed_of_sound_response(self, response, prompt):
        """
        """

    def _parse_raw_mode_response(self, response, prompt):
        """
        """

    def _parse_real_mode_response(self, response, prompt):
        """
        """

    def _parse_single_scan_response(self, response, prompt):
        """
        """

    def _parse_clear_fault_log_response(self, response, prompt):
        """
        """

    def _parse_fault_log_response(self, response, prompt):
        """
        """

    def _parse_fault_log_toggle_response(self, response, prompt):
        """
        """

    def _parse_depolyment_tests(self, response, prompt):
        """
        """

    def _parse_beam_continuity_test(self, response, prompt):
        """
        """

    def _parse_heading_pitch_roll_orientation_test_results(self, response, prompt):
        """
        """

    def _parse_system_configuration_response(self, response, prompt):
        """
        """

    def _parse_instrument_transform_matrix_response(self, response, prompt):
        """
        """

    def _parse_test_response(self, response, prompt):
        """
        """

    def _parse_time_response(self, response, prompt):
        """
        """
        log.debug("_parse_time_response RESPONSE = %s", response)
        for line in response.split(NEWLINE):
            hit_count = self._param_dict.multi_match_update(line)
    ########################################################################
    # handlers.
    ########################################################################



    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.

        log.debug("*** IN _handler_command_enter(), updating params")
        #self._update_params() #errors when enabled

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result), (ProtocolState.COMMAND or
        State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """
        log.debug("IN _handler_unknown_discover")

        timeout = kwargs.get('timeout', TIMEOUT)

        next_state = None
        result = None

        current_state = self._protocol_fsm.get_current_state()

        #logging = self._is_logging(timeout=timeout)

        #if logging == True:
        #    next_state = ProtocolState.AUTOSAMPLE
        #    result = ResourceAgentState.STREAMING
        #elif logging == False:
        log.debug("THIS IS RIGGED!")
        next_state = ProtocolState.COMMAND
        result = ResourceAgentState.IDLE
        #else:
        #    raise InstrumentStateException('Unknown state.')

        self._update_params()
        return (next_state, result)

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from SBE26 Plus.
        @retval (next_state, result) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """

        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 45 # samples can take a long time

        result = self._do_cmd_resp(InstrumentCmds.TAKE_SAMPLE, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state.
        """
        pass

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        kwargs['expected_prompt'] = Prompt.COMMAND
        kwargs['timeout'] = 30

        next_state = None
        result = None

        # Issue start command and switch to autosample if successful.
        self._start_logging()

        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return (next_state, (next_agent_state, result))

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', TIMEOUT)
        self._wakeup_until(timeout, Prompt.AUTOSAMPLE)

        self._stop_logging(timeout)

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    def _handler_command_autosample_test_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @throws InstrumentParameterException if missing or invalid parameter.
        """
        log.debug("IN _handler_command_autosample_test_get " + str(args) + " <>" + str(kwargs))
        next_state = None
        result = None

        # Retrieve the required parameter, raise if not present.
        try:
            params = args[0]

        except IndexError:
            raise InstrumentParameterException('Get command requires a parameter list or tuple.')

        # If all params requested, retrieve config.
        if params == DriverParameter.ALL or DriverParameter.ALL in params:
            result = self._param_dict.get_config()

        # If not all params, confirm a list or tuple of params to retrieve.
        # Raise if not a list or tuple.
        # Retireve each key in the list, raise if any are invalid.

        else:
            if not isinstance(params, (list, tuple)):
                raise InstrumentParameterException('Get argument not a list or tuple.')
            result = {}
            for key in params:
                val = self._param_dict.get(key)
                result[key] = val

        return (next_state, result)

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
        error = None

        try:
            # Switch to command mode,
            self._stop_logging()

            # Sync the clock
            timeout = kwargs.get('timeout', TIMEOUT)
            self._sync_clock(Parameter.DS_DEVICE_DATE_TIME, Prompt.COMMAND, timeout)

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging()

        if(error):
            raise error

        return (next_state, (next_agent_state, result))

    def _handler_command_set(self, *args, **kwargs):
        """
        Perform a set command.
        @param args[0] parameter : value dict.
        @retval (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set parameters not ALL and
        not a dict, or if paramter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
        next_state = None
        result = None
        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        else:
            self._set_params(params)

        return (next_state, result)

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.

        kwargs['expected_prompt'] = Prompt.COMMAND

        startup = False
        try:
            set_params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        try:
            startup = args[1]
        except IndexError:
            pass

        # Only check for readonly parameters if we are not setting them from startup
        if not startup:
            readonly = self._param_dict.get_visibility_list(ParameterDictVisibility.READ_ONLY)

            log.debug("set param, but check visibility first")
            log.debug("Read only keys: %s" % readonly)

            for (key, val) in set_params.iteritems():
                if key in readonly:
                    raise InstrumentParameterException("Attempt to set read only parameter (%s)" % key)

        log.debug("General Set Params: %s" % set_params)

        if set_params != {}:
            for (key, val) in set_params.iteritems():
                log.debug("KEY = " + str(key) + " VALUE = " + str(val))
                result = self._do_cmd_resp(InstrumentCmds.SET, key, val, **kwargs)

                result = self._do_cmd_resp(InstrumentCmds.GET, key, **kwargs)
                log.debug("RESULT should be empty %s", result)
        #self._update_params()

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        log.debug("IN _handler_command_acquire_status - DOING NOTHING I GUESS")
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30

        #cmds = [Parameter.TIME, Parameter.INSTRUMENT_ID]

        #for key in cmds:
        #    self._do_cmd_resp(InstrumentCmds.GET, key, **kwargs)




        return (next_state, (next_agent_state, result))


    def _handler_command_acquire_configuration(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        result = self._do_cmd_resp(InstrumentCmds.DISPLAY_CALIBRATION, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_command_quit_session(self, *args, **kwargs):
        """
        Perform a command-response on the device.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional wakeup and command timeout.
        @retval resp_result The (possibly parsed) response result.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """

        next_state = None
        result = None

        result = self._do_cmd_no_resp(InstrumentCmds.QUIT_SESSION, *args, **kwargs)
        return (next_state, result)

    def _handler_command_clock_sync(self, *args, **kwargs):
        """
        execute a clock sync on the leading edge of a second change
        @retval (next_state, result) tuple, (None, (None, )) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None

        timeout = kwargs.get('timeout', TIMEOUT)
        self._sync_clock(Parameter.DS_DEVICE_DATE_TIME, Prompt.COMMAND, timeout)

        return (next_state, (next_agent_state, result))

    def _handler_command_send_last_sample(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        result = self._do_cmd_resp(InstrumentCmds.SEND_LAST_SAMPLE, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_command_start_direct(self, *args, **kwargs):
        """
        """
        next_state = None
        result = None

        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS

        return (next_state, (next_agent_state, result))

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        pass

    def _handler_direct_access_execute_direct(self, data):
        """
        """
        next_state = None
        result = None
        next_agent_state = None

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return (next_state, (next_agent_state, result))

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """

        next_state = None
        result = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))


    def _build_set_command(self, cmd, param, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        @ retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        try:
            str_val = self._param_dict.format(param, val)
            set_cmd = '%s%s' % (param, str_val)
            set_cmd = set_cmd + NEWLINE
            log.debug("IN _build_set_command CMD = '%s'", set_cmd)
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return set_cmd


    def _parse_set_response(self, response, prompt):
        """
        Parse handler for set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """

        if prompt == Prompt.ERR:
            raise InstrumentProtocolException('Protocol._parse_set_response : Set command not recognized: %s' % response)







    def _build_get_command(self, cmd, param, **kwargs):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        @ retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        
        log.debug("in _build_get_command")
        try:
            get_cmd = param + '?' + NEWLINE
            log.debug("IN _build_get_command CMD = '%s'", get_cmd)
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return get_cmd






    def _parse_get_response(self, response, prompt):
        log.debug("in _parse_get_response RESPONSE = %s", str(response) + str(prompt) )
        if prompt == Prompt.ERR:
            raise InstrumentProtocolException('Protocol._parse_set_response : Set command not recognized: %s' % response)

        if " ERR " in response:
            raise InstrumentProtocolException('Protocol._parse_set_response : Set command not recognized: %s' % response)
        
        self._param_dict.update(response)
        for line in response.split(NEWLINE):
            log.debug("Scanning line through param_dict -> %s", line)
            self._param_dict.update(line)




