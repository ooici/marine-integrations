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
from mi.core.exceptions import SampleException

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
ADCP_PD0_PARSED_REGEX = r'\x7f\x7f(.*)' #(.{230})' #2152 total...
ADCP_PD0_PARSED_REGEX_MATCHER = re.compile(ADCP_PD0_PARSED_REGEX, re.DOTALL)

ADCP_SYSTEM_CONFIGURATION_REGEX = r'(Instrument S/N.*?)\>'
ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER = re.compile(ADCP_SYSTEM_CONFIGURATION_REGEX, re.DOTALL)

ADCP_COMPASS_CALIBRATION_REGEX = r'(ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM.*?)\>'
ADCP_COMPASS_CALIBRATION_REGEX_MATCHER = re.compile(ADCP_COMPASS_CALIBRATION_REGEX, re.DOTALL)

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
    ABSOLUTE_PRESSURE = "absolute_pressure"
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
        log.debug("IN ADCP_PD0_PARSED_DataParticle _build_parsed_values")

        self.final_result = []

        length = unpack("H", self.raw_data[2:4])[0]
        log.debug("LENGTH %s, %s ..", str(length), str(len(self.raw_data[2:])))

        data = str(self.raw_data)
        #
        # Calculate Checksum
        #
        total = int(0)
        for i in range(0, length):
            total += int(ord(data[i]))

        checksum = total & 65535    # bitwise and with 65535 or mod vs 65536

        if checksum != unpack("H", self.raw_data[length: length+2])[0]:
            raise Exception

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
            log.debug("variable_leader_id = %s", str(variable_leader_id))
            log.debug("OBTAINING CHUNK %s FROM %s TO %s FOR A LENGTH OF %s", 
                      str(offset),
                      str(offsets[offset]),
                      str(offsets[offset + 1]),
                      str(len(chunks[offset])))
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

        self.coord_transform_type = coord_transform_type  # lame, but expedient

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
            raise SampleException("coord_transform_type not coded for.")

    def parse_corelation_magnitude_chunk(self, chunk):
        """
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
            raise SampleException("coord_transform_type not coded for.")

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

    EF_CHAR = '\xef'

    RE01 = re.compile(r' +Calibration date and time: ([/0-9: ]+)')
    RE04 = re.compile(r' +Bx +# +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) #')
    RE05 = re.compile(r' +By +# +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) #')
    RE06 = re.compile(r' +Bz +# +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) #')
    RE07 = re.compile(r' +Err +# +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) +([0-9e+-.]+) #')

    RE11 = re.compile(r' +# +([0-9e+-.]+) +#')
    RE12 = re.compile(r' +# +([0-9e+-.]+) +#')
    RE13 = re.compile(r' +# +([0-9e+-.]+) +#')
    RE14 = re.compile(r' +# +([0-9e+-.]+) +#')

    RE18 = re.compile(r' +# ([0-9.]+) #')
    RE21 = re.compile(r' +Calibration date and time: ([/0-9: ]+)')
    RE22 = re.compile(r' +Average Temperature During Calibration was +([0-9.]+) #')
    RE27 = re.compile(r' Roll +# +([0-9e+-.]+) +([0-9e+-.]+) +# +# +([0-9e+-.]+) +([0-9e+-.]+) +#')
    RE28 = re.compile(r' Pitch +# +([0-9e+-.]+) +([0-9e+-.]+) +# +# +([0-9e+-.]+) +([0-9e+-.]+) +#')
    RE32 = re.compile(r' Offset # +([0-9e+-.]+) +([0-9e+-.]+) +# +# +([0-9e+-.]+) +([0-9e+-.]+) +#')
    RE36 = re.compile(r' +Null +# (\d+) +#')

    def _build_parsed_values(self):
        """
        """
        # Initialize
        matches = {}

        lines = self.raw_data.replace(self.EF_CHAR,'#').split(NEWLINE)

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
            if matcher == ADCP_PD0_PARSED_REGEX_MATCHER:
                #
                # Have to cope with variable length binary records...
                # lets grab the length, then write a proper query to
                # snag it.
                #
                matcher = re.compile(r'\x7f\x7f(..)', re.DOTALL)
                for match in matcher.finditer(raw_data):
                    l = unpack("H", match.group(1))
                    log.debug("LEN IS = %s", str(l[0]))
                    outer_pos = match.start()
                    log.debug("MATCH START = " + str(outer_pos))
                    ADCP_PD0_PARSED_TRUE_MATCHER = re.compile(r'\x7f\x7f(.{' + str(l[0]) + '})', re.DOTALL)


                    for match in ADCP_PD0_PARSED_TRUE_MATCHER.finditer(raw_data, outer_pos):
                        inner_pos = match.start()
                        log.debug("INNER MATCH START = " + str(inner_pos))
                        if (outer_pos == inner_pos):
                            return_list.append((match.start(), match.end()))
                    """
                    match_iter = ADCP_PD0_PARSED_TRUE_MATCHER.finditer(raw_data, pos)
                    match_iter.
                    match = match_iter.next()
                    return_list.append((match.start(), match.end()))
                    """
            else:
                for match in matcher.finditer(raw_data):
                    log.debug("MATCHED!!!!! %d .. %d", match.start(), match.end())
                    return_list.append((match.start(), match.end()))

        return return_list

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with sbe26plus parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """

        self._param_dict.add(Parameter.SERIAL_DATA_OUT,
            r'CD = (\d\d\d \d\d\d \d\d\d) \-+ Serial Data Out ',
            lambda match: str(match.group(1)),
            self._string_to_string,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.SERIAL_FLOW_CONTROL,
            r'CF = (\d+) \-+ Flow Ctrl ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=11110)

        self._param_dict.add(Parameter.BANNER,
            r'CH = (\d) \-+ Suppress Banner',
            lambda match: not bool(int(match.group(1), base=10)),
            self._reverse_bool_to_int,
            startup_param=True,
            default_value=True)

        self._param_dict.add(Parameter.INSTRUMENT_ID,
            r'CI = (\d+) \-+ Instrument ID ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True)

        self._param_dict.add(Parameter.SLEEP_ENABLE,
            r'CL = (\d) \-+ Sleep Enable',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=False)

        self._param_dict.add(Parameter.SAVE_NVRAM_TO_RECORDER,
            r'CN = (\d) \-+ Save NVRAM to recorder',
            lambda match: bool(int(match.group(1), base=10)),
            self._bool_to_int,
            startup_param=True,
            default_value=True,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.POLLED_MODE,
            r'CP = (\d) \-+ PolledMode ',
            lambda match: bool(int(match.group(1), base=10)),
            self._bool_to_int,
            startup_param=True,
            default_value=False)

        self._param_dict.add(Parameter.XMIT_POWER,
            r'CQ = (\d+) \-+ Xmt Power ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=255)

        self._param_dict.add(Parameter.SPEED_OF_SOUND,
            r'EC = (\d+) \-+ Speed Of Sound',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=1485)

        self._param_dict.add(Parameter.PITCH,
            r'EP = ([\+\-\d]+) \-+ Tilt 1 Sensor ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.ROLL,
            r'ER = ([\+\-\d]+) \-+ Tilt 2 Sensor ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.SALINITY,
            r'ES = (\d+) \-+ Salinity ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=35)

        self._param_dict.add(Parameter.SENSOR_SOURCE,
            r'EZ = (\d+) \-+ Sensor Source ',
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True)

        self._param_dict.add(Parameter.TIME_PER_ENSEMBLE,
            r'TE (\d\d:\d\d:\d\d.\d\d) \-+ Time per Ensemble ',
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True,
            default_value='00:00:00.00')

        self._param_dict.add(Parameter.TIME_OF_FIRST_PING,
            r'TG (..../../..,..:..:..) - Time of First Ping ',
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
            r'WA (\d+,\d+) \-+ False Target Threshold ',
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True,
            default_value='050,001')

        self._param_dict.add(Parameter.BANDWIDTH_CONTROL,
            r'WB (\d) \-+ Bandwidth Control ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.CORRELATION_THRESHOLD,
            r'WC (\d+) \-+ Correlation Threshold',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=64)

        self._param_dict.add(Parameter.SERIAL_OUT_FW_SWITCHES,
            r'WD ([\d ]+) \-+ Data Out ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            visibility=ParameterDictVisibility.READ_ONLY,
            startup_param=True,
            default_value='111100000')

        self._param_dict.add(Parameter.ERROR_VELOCITY_THRESHOLD,
            r'WE (\d+) \-+ Error Velocity Threshold',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=2000)

        self._param_dict.add(Parameter.BLANK_AFTER_TRANSMIT,
            r'WF (\d+) \-+ Blank After Transmit',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=704)

        self._param_dict.add(Parameter.CLIP_DATA_PAST_BOTTOM,
            r'WI (\d) \-+ Clip Data Past Bottom',
            lambda match: bool(int(match.group(1), base=10)),
            self._bool_to_int,
            startup_param=True,
            default_value=False)

        self._param_dict.add(Parameter.RECEIVER_GAIN_SELECT,
            r'WJ (\d) \-+ Rcvr Gain Select \(0=Low,1=High\)',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=1)

        self._param_dict.add(Parameter.WATER_REFERENCE_LAYER,
            r'WL (\d+,\d+) \-+ Water Reference Layer:  ',
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True,
            default_value='001,005')

        self._param_dict.add(Parameter.WATER_PROFILING_MODE,
            r'WM (\d+) \-+ Profiling Mode ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            visibility=ParameterDictVisibility.READ_ONLY,
            startup_param=True,
            default_value=1)

        self._param_dict.add(Parameter.NUMBER_OF_DEPTH_CELLS,
            r'WN (\d+) \-+ Number of depth cells',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=100)

        self._param_dict.add(Parameter.PINGS_PER_ENSEMBLE,
            r'WP (\d+) \-+ Pings per Ensemble ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=1)

        self._param_dict.add(Parameter.DEPTH_CELL_SIZE,
            r'WS (\d+) \-+ Depth Cell Size \(cm\)',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=800)

        self._param_dict.add(Parameter.TRANSMIT_LENGTH,
            r'WT (\d+) \-+ Transmit Length ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.PING_WEIGHT,
            r'WU (\d) \-+ Ping Weighting ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=0)

        self._param_dict.add(Parameter.AMBIGUITY_VELOCITY,
            r'WV (\d+) \-+ Mode 1 Ambiguity Vel ',
            lambda match: int(match.group(1), base=10),
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

        if " ERR" in response:
            raise InstrumentParameterException('Protocol._parse_set_response : Set command failed: %s' % response)






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

        self._param_dict.update(response)
        for line in response.split(NEWLINE):
            log.debug("Scanning line through param_dict -> %s", line)
            self._param_dict.update(line)




