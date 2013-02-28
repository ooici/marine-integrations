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
import time
import string
import ntplib
from datetime import *

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
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

ENSEMBLE_REGEX = r'7F7F'
ENSEMBLE_REGEX_MATCHER = re.compile(ENSEMBLE_REGEX)

CALIBRATION_DATA_REGEX = r'ACTIVE FLUXGATE CALIBRATION MATRICES(.*?\n)*?>'
CALIBRATION_DATA_REGEX_MATCHER = re.compile(CALIBRATION_DATA_REGEX)

PS0_REGEX = r'Instrument S(.*?\n)*?>'
PS0_REGEX_MATCHER = re.compile(PS0_REGEX)

PS3_REGEX = r'Beam Width:(.*?\n)*?>'
PS3_REGEX_MATCHER = re.compile(PS3_REGEX)

FD_REGEX = r'Total Unique Faults(.*?\n)*?>'
FD_REGEX_MATCHER = re.compile(FD_REGEX)

PT200_REGEX = r'Ambient(.*?\n)*?>'
PT200_REGEX_MATCHER = re.compile(PT200_REGEX)

BREAK_SUCCESS_REGEX = r'BREAK Wakeup A(.*?\n)*?>'
BREAK_SUCCESS_REGEX_MATCHER = re.compile(BREAK_SUCCESS_REGEX)

BREAK_ALARM_REGEX = r'ALARM Wakeup A(.*?\n)*?>'
BREAK_ALARM_REGEX_MATCHER = re.compile(BREAK_ALARM_REGEX)

POWERING_DOWN_REGEX = r'Powering Down'
POWERING_DOWN_REGEX_MATCHER = re.compile(POWERING_DOWN_REGEX)

ERR_REGEX = r'ERR(.*?\n)*?>'
ERR_REGEX_MATCHER = re.compile(ERR_REGEX)



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

    BREAK = 'break 500'
    ZERO_PRESSURE_READING = 'AZ'
    FAULT_DEBUG = 'FX'                  # toggles debug flag.. <------ problem?
    EXPERT_ON = 'EXPERTON'
    EXPERT_OFF = 'EXPERTOFF'
    LIST_FIRMWARE_UPGRADES = 'OL'
    OUTPUT_CALIBRATION_DATA = 'AC'
    OUTPUT_FACTORY_CALIBRATION_DATA = 'AD'
    FIELD_CALIBRATE_COMPAS = 'AF'
    LOAD_FACTORY_CALIBRATION = 'AR'
    ZERO_PRESSURE_SENSOR = 'AZ'
    CHOOSE_EXTERNAL_DEVICES = 'CC'
    SEND_LAST_DATA_ENSEMBLE = 'CE'
    SAVE_SETUP_TO_RAM = 'CK'
    RETRIEVE_PARAMETERS = 'CR'
    START_DEPLOYMENT = 'CS'
    CLEAR_ERROR_STATUS_WORD = 'CY0'
    DISPLAY_ERROR_STATUS_WORD = 'CY1'
    POWER_DOWN = 'CZ'
    LOAD_SPEED_OF_SOUND = 'DS'
    GO_RAW_MODE = 'DX'
    GO_REAL_MODE = 'DY'
    GET_SINGLE_SCAN = 'DZ'
    CLEAR_FAULT_LOG = 'FC'
    DISPLAY_FAULT_LOG = 'FD'
    TOGGLE_FAULT_LOG_DEBUG = 'FX'
    RUN_PRE_DEPLOYMENT_TESTS = 'PA'
    RUN_BEAM_CONTINUITY_TEST = 'PC1'
    SHOW_HEADING_PITCH_ROLL_ORIENTATION_TEST_RESULTS = 'PC2'
    GET_SYSTEM_CONFIGURATION = 'PS0'
    GET_INSTRUMENT_TRANSFORM_MATRIX = 'PS3'
    RUN_TEST = 'PT'


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    TEST = DriverProtocolState.TEST
    POLL = DriverProtocolState.POLL


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

    #BREAK_ALARM = 'BREAK_ALARM'  ???
    #BREAK_SUCCESS = 'BREAK_SUCCESS'
    #SELF_DEPLOY = 'SELF_DEPLOY'
    #POWERING_DOWN = 'POWERING_DOWN'


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
    SETSAMPLING = ProtocolEvent.SETSAMPLING
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
    TEST = ProtocolEvent.TEST


class Parameter(DriverParameter):
    """
    Device parameters
    """
    #
    # set-able parameters
    #
    INSTRUMENT_ID = 'CI'                # Int 0-255
    POLLED_MODE = 'CP'                  # 1=ON, 0=OFF;
    XMIT_POWER = 'CQ'                   # 0=Low, 255=High
    TIME_PER_BURST = 'TB'               # 00:00:00.00  (hrs:min:sec.sec/100)
    ENSEMBLES_PER_BURST = 'TC'          # 0-65535
    TIME_PER_ENSEMBLE = 'TE'            # 01:00:00.00 (hrs:min:sec.sec/100)
    TIME_OF_FIRST_PING = 'TF'           # **/**/**,**:**:**  (yr/mon/day,hour:min:sec)
    TIME_OF_FIRST_PING_Y2K = 'TG'       # ****/**/**,**:**:** (CCYY/MM/DD,hh:mm:ss)
    TIME_PER_PING = 'TP'                # 00:00.20  (min:sec.sec/100)
    #TIME = 'TS'                        # 13/02/22,13:18:09 (yr/mon/day,hour:min:sec)
    TIME = 'TT'                         # 2013/02/26,05:28:23 (CCYY/MM/DD,hh:mm:ss)
    BUFFERED_OUTPUT_PERIOD = 'TX'       # 00:00:00 (hh:mm:ss)
    FALSE_TARGET_THRESHOLD = 'WA'       # 255,001 (Max)(0-255),Start Bin # <--------- TRICKY.... COMPLEX TYPE
    CORRELATION_THRESHOLD = 'WC'        # 064  Correlation Threshold
    SERIAL_OUT_FW_SWITCHES = 'WD'       # 111100000  Data Out (Vel;Cor;Amp PG;St;P0 P1;P2;P3)
    ERROR_VELOCITY_THRESHOLD = 'WE'     # 5000  Error Velocity Threshold (0-5000 mm/s)
    BLANK_AFTER_TRANSMIT = 'WF'         # 0088  Blank After Transmit (cm)
    CLIP_DATA_PAST_BOTTOM = 'WI'        # 0 Clip Data Past Bottom (0=OFF,1=ON)
    RECEIVER_GAIN_SELECT = 'WJ'         # 1  Rcvr Gain Select (0=Low,1=High)
    WATER_REFERENCE_LAYER = 'WL'        # 001,005  Water Reference Layer: Begin Cell (0=OFF), End Cell
    WATER_PROFILING_MODE = 'WM'         # Profiling Mode (1-15)
    NUMBER_OF_DEPTH_CELLS = 'WN'        #Number of depth cells (1-255)
    PINGS_PER_ENSEMBLE = 'WP'           # Pings per Ensemble (0-16384)
    DEPTH_CELL_SIZE = 'WS'              # 0800  Depth Cell Size (cm)
    TRANSMIT_LENGTH = 'WT'              # 0000 Transmit Length 0 to 3200(cm) 0 = Bin Length
    PING_WEIGHT = 'WU'                  # 0 Ping Weighting (0=Box,1=Triangle)
    AMBIGUITY_VELOCITY = 'WV'           # 175 Mode 1 Ambiguity Vel (cm/s radial)
    CHOOSE_EXTERNAL_DEVICE = 'CC'       # 000 000 000 or 000 000 001 Choose External Devices (x;x;x x;x;x x;x;SBMC)
    BANNER = 'CH'                       # Suppress Banner 0=Show, 1=Suppress
    IMM_OUTPUT_ENABLE = 'CJ'            # IMM Output Enable (0=Disable,1=Enable)
    SLEEP_ENABLE = 'CL'                 # Sleep Enable (0 = Disable, 1 = Enable, 2 See Manual)
    SERIAL_SYNC_MASTER = 'CM'           # RS-232 Sync Master (0 = OFF, 1 = ON)
    SAVE_NVRAM_TO_RECORDER = 'CN'       # Save NVRAM to recorder (0 = ON, 1 = OFF)
    TRIGGER_TIMEOUT = 'CW'              # Trigger Timeout (ms; 0 = no timeout)
    LOW_LATENCY_TRIGGER_ENABLE = 'CX'   # Trigger Enable (0 = OFF, 1 = ON)
    HEADING_ALIGNMENT = 'EA'            # Heading Alignment (1/100 deg) -17999 to 18000
    HEADING_BIAS = 'EB'                 # Heading Bias (1/100 deg) -17999 to 18000
    SPEED_OF_SOUND = 'EC'               # 1500  Speed Of Sound (m/s)
    TRANSDUCER_DEPTH = 'ED'             # Transducer Depth (0 - 65535 dm)
    HEADING = 'EH'                      # Heading (1/100 deg) 0 to 35999 (000.00 to 359.99 degrees)
    PITCH = 'EP'                        # Tilt 1 Sensor (1/100 deg) -6000 to 6000 (-60.00 to +60.00 degrees)
    ROLL = 'ER'                         # Tilt 2 Sensor (1/100 deg) -6000 to 6000 (-60.00 to +60.00 degrees)
    SALINITY = 'ES'                     # 35 (0-40 pp thousand)
    TEMPERATURE = 'ET'                  # Temperature (1/100 deg Celsius) -500 to 4000 (-5.00 C to +40.00 C)
    COORDINATE_TRANSFORMATION = 'EX'    # Coord Transform (Xform:Type; Tilts; 3Bm; Map)
    SENSOR_SOURCE = 'EZ'                # Sensor Source (C;D;H;P;R;S;T)

    OUTPUT_BIN_SELECTION = 'PB'         # PD12 Bin Select (first;num;sub) x 1 to 128 y 0 to 128z 1 to 7 [start, every nth, total count]
    DATA_STREAM_SELECT = 'PD'           # Data Stream Select (0-18)
    ENSEMBLE_SELECT = 'PE'              # PD12 Ensemble Select (1-65535)
    VELOCITY_COMPONENT_SELECT = 'PO'    # PD12 Velocity Component Select (0 OR 1 FOR v1;v2;v3;v4) AFFECTED BY EX
    SYNCHRONIZE = 'SA'                  # Synch Before/After Ping/Ensemble Bottom/Water/Both
    BREAK_INTERUPTS = 'SB'              # Channel B Break Interrupts 0 Disabled 1 ENABLED
    SYNC_INTERVAL = 'SI'                # Synch Interval (0-65535)
    MODE_SELECT = 'SM'                  # Mode Select (0=OFF,1=MASTER,2=SLAVE,3=NEMO)'
    RDS3_SLEEP_MODE = 'SS'              # RDS3 Sleep Mode (0=No Sleep)
    SLAVE_TIMEOUT = 'ST'                # Slave Timeout (seconds,0=indefinite)
    SYNC_DELAY = 'SW'                   # Synch Delay (1/10 msec) 0 to 65535 (units of 0.1 milliseconds)
    DEVICE_485_ID = 'DW'                # Current ID on RS-485 Bus (0 to 31)
    DEPLOYMENT_AUTO_INCRIMENT = 'RI'    # Auto Increment Deployment File (0=Disable,1=Enable)
    DEPLOYMENT_NAME = 'RN'              # Set Deployment Name
    BANDWIDTH_CONTROL = 'WB'            # Bandwidth Control (0=Wid,1=Nar)
    WANTED_GOOD_PERCENT = 'WG'          # Percent Good Minimum (1-100%)  Contains the minimum percentage of water-profiling pings in an ensemble that must be considered good to output velocity data.
    SAMPLE_AMBIENT_SOUND = 'WQ'         # Sample Ambient Sound (0=OFF,1=ON)
    PINGS_BEFORE_REAQUIRE = 'WW'        # Mode 1 Pings before Mode 4 Re-acquire
    MODE_5_AMBIGUITY_VELOCITY = 'WZ'    # Mode 5 Ambiguity Velocity (cm/s radial)

    #
    # Read Only Vars
    #

    ZERO_PRESSURE_READING = 'AZ'        #  Zero pressure reading' (RO) ALSO a command
    SERIAL_PORT_CONTROL = 'CB'          # 411 \Serial Port Control (Baud 4=9600; Par; Stop)'
    SERIAL_DATA_OUT = 'CD'              # 000 000 000 Serial Data Out (Vel;Cor;Amp PG;St;P0 P1;P2;P3)
    SERIAL_FLOW_CONTROL = 'CF'          # 11110  Flow Ctrl (EnsCyc;PngCyc;Binry;Ser;Rec)
    SERIAL_485_BAUD = 'DB'              # RS-485 Port Control (Baud; N/U; N/U) Baud = 1 to 7 (300 to 57600)
    DEPLOYMENTS_RECORDED = 'RA'         # Number of Deployments Recorded


class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """
    COMMAND = '>'
    AUTOSAMPLE = ''
    ERR = 'ERR:'

###############################################################################
# Data Particles
###############################################################################
class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    ENSEMBLE_PARSED = 'ensemble_parsed'
    CALIBRATION_PARSED = 'calibration_parsed'
    PS0_PARSED = 'ps0_parsed'
    PS3_PARSED = 'ps3_parsed'
    FD_PARSED = 'fd_parsed'
    PT200_PARSED = 'pt200_parsed'

class ADCPT_PS0DataParticleKey(BaseEnum):
    PS0_DATA = "ps0_data"


class ADCPT_PS0DataParticle(DataParticle):
    _data_particle_type = DataParticleType.PS0_PARSED

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


class ADCPT_PS3DataParticleKey(BaseEnum):
    PS3_DATA = "ps3_data"


class ADCPT_PS3DataParticle(DataParticle):
    _data_particle_type = DataParticleType.PS3_PARSED

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


class ADCPT_FDDataParticleKey(BaseEnum):
    FD_DATA = "fd_data"


class ADCPT_FDDataParticle(DataParticle):
    _data_particle_type = DataParticleType.FD_PARSED

    def _build_parsed_values(self):

        data_stream = self.raw_data
        m = re.search(FD_REGEX, data_stream)
        if m is not None:
            # don't put the '>' in the data particle
            value = m.group()[:-1]
        else:
            value = None
        result = [{DataParticleKey.VALUE_ID: ADCPT_FDDataParticleKey.FD_DATA,
                   DataParticleKey.VALUE: value}]
        return result


class ADCPT_PT200DataParticleKey(BaseEnum):
    PT200_DATA = "pt200_data"


class ADCPT_PT200DataParticle(DataParticle):
    _data_particle_type = DataParticleType.PT200_PARSED

    def _build_parsed_values(self):

        data_stream = self.raw_data
        m = re.search(PT200_REGEX, data_stream)
        if m is not None:
            # don't put the '>' in the data particle
            value = m.group()[:-1]
        else:
            value = None
        result = [{DataParticleKey.VALUE_ID: ADCPT_PT200DataParticleKey.PT200_DATA,
                   DataParticleKey.VALUE: value}]
        return result


class ADCPT_CalibrationDataParticleKey(BaseEnum):
    CALIBRATION_DATA = "calibration_data"


class ADCPT_CalibrationDataParticle(DataParticle):
    _data_particle_type = DataParticleType.CALIBRATION_PARSED

    def _build_parsed_values(self):

        data_stream = self.raw_data
        m = re.search(CALIBRATION_DATA_REGEX, data_stream)
        if m is not None:
            # don't put the '>' in the data particle
            value = m.group()[:-1]
            value = value.replace('\xef', '?')
        else:
            value = None
        result = [{DataParticleKey.VALUE_ID: ADCPT_CalibrationDataParticleKey.CALIBRATION_DATA,
                   DataParticleKey.VALUE: value}]
        return result


class ADCPT_EnsembleDataParticleKey(BaseEnum):
    NUM_BYTES_IN_ENSEMBLE = "Ensemble bytes"
    NUM_DATA_TYPES = "NumTypes"

    #-------fixed leader data format------------
    CPU_FW_VER = "CPU_fw_ver"
    CPU_FW_REV = "CPU_fw_rev"
    SYS_CONFIG = "SysConfig"
    LAG_LEN = "LagLength"
    NUM_BEAMS = "NumBeams"
    NUM_CELLS = "NumCells"
    PINGS_PER_ENSEMBLE = "Pings_per_ensemble"
    DEPTH_CELL_LEN = "Depth_cell_length"
    BLANK_AFTER_TX = "Blank_after_transmit"
    PROFILING_MODE = "Profiling_Mode"
    LOW_CORR_THRESH = "Low_correlation_threshold"
    NUM_CODE_REPS = "Number_of_code_repetitions"
    PERCENT_GD_MIN = "Percent_of_GD_minimum"
    ERR_VEL_MAX = "Error_velocity_maximum"
    TIME_BETWEEN_PINGS = "Time_between_pings"
    COORD_XFRM = "Coordinate_transform"
    HEAD_ALIGN = "Heading_alignment"
    HEAD_BIAS = "Heading_bias"
    #SENSOR_SRC = "Sensor_source"

    CALC_SPD_SND_FROM_DATA = "Calc_spd_snd_from_data"
    USE_DEPTH_FROM_SENSOR = "Use_depth_from_sensor"
    USE_HEADING_FROM_SENSOR = "Use_heading_from_sensor"
    USE_PITCH_FROM_SENSOR = "Use_pitch_from_sensor"
    USE_ROLL_FROM_SENSOR = "Use_roll_from_sensor"
    USE_SALINITY_FROM_SENSOR = "Use_salinity_from_sensor"
    USE_TEMPERATURE_FROM_SENSOR = "Use_temperature_from_sensor"

    #SENSOR_AVAIL = "Sensor_availability"

    DEPTH_SENSOR_AVAIL = "Depth_sensor_avail"
    HEADING_SENSOR_AVAIL = "Heading_sensor_avail"
    PITCH_SENSOR_AVAIL = "Pitch_sensor_avail"
    ROLL_SENSOR_AVAIL = "Roll_sensor_avail"
    SALINITY_SENSOR_AVAIL = "Salinity_sensor_avail"
    TEMPERATURE_SENSOR_AVAIL = "Temperature_sensor_avail"

    BIN1_DIST = "Distance_to_bin_1"
    XMIT_PULSE_LEN = "Xmit_Pulse_Length"
    WP_REF_LAYER_AVG = "WP_ref_layer_avg"
    FALSE_TARGET_THRESH = "False_Target_Threshold"
    XMIT_LAG_DIST = "Transmit_Lag_Distance"
    CPU_SN = "CPU_board_serial_number"
    SYS_BW = "System_Bandwidth"
    SYS_PWR = "System_Power"
    INST_SN = "Instrument_Serial_Number"
    BEAM_ANGLE = "Beam_Angle"

    #-------var leader data format------------
    ENSEMBLE_NUMBER = "Ensemble_Number"
    RTC_DATE_TIME = "RTC_date_time"
    TIMESTAMP = "timestamp"
    ENSEMBLE_NUM_MSB = "Ensemble_number_msb"
    BIT_RESULT = "Built_in_Test_Results"
    SPEED_OF_SOUND = "Speed_of_sound"
    DEPTH_OF_XDUCER = "Depth_of_transducer"
    HEADING = "Heading"
    PITCH = "Pitch"
    ROLL = "Roll"
    SALINITY = "Salinity"
    TEMPERATURE = "Temperature"
    MIN_PRE_PING_WAIT_TIME = "Min_pre_ping_wait_time"
    HDG_DEV = "Heading_deviation"
    PITCH_DEV = "Pitch_deviation"
    ROLL_DEV = "Roll_deviation"
    XMIT_CURRENT = "Xmit_current"
    XMIT_VOLTAGE = "Xmit_voltage"
    AMBIENT_TEMP = "Ambient_temp"
    PRESSURE_POS = "Pressure_pos"
    PRESSURE_NEG = "Pressure_neg"
    ATTITUDE_TEMP = "Attitude_temp"
    ATTITUDE = "Attitude"
    CONTAMINATION_SENSOR = "Combination_sensor"
    BUS_ERR = "Bus_error"
    ADDR_ERR = "Address_error"
    ILLEGAL_INSTR = "Illegal_instruction"
    ZERO_DIV = "Divide_by_zero"
    EMUL_EXCEP = "Emulator_exception"
    UNASS_EXCEP = "Unassigned_exception"
    WATCHDOG = "Watchdog"
    BATT_SAVE_PWR = "Battery_save_power"
    PINGING = "Pinging"
    COLD_WAKEUP = "Cold_wakeup"
    UNKNOWN_WAKEUP = "Unknown_wakeup"
    CLOCK_RD_ERR = "Clock_read_error"
    UNEXP_ALARM = "Unexpected_alarm"
    CLOCK_JMP_FWD = "Clock_jump_forward"
    CLOCK_JMP_BKWRD = "Clock_jump_backward"
    PWR_FAIL = "Power_fail"
    SPUR_4_INTR = "Spurious_4_interrupt"
    SPUR_5_INTR = "Spurious_5_interrupt"
    SPUR_6_INTR = "Spurious_6_interrupt"
    LEV_7_INTR = "Level_7_interrupt"
    PRESSURE = "Pressure"
    PRESSURE_VAR = "Pressure_sensor_variance"
    RTCY2K_DATE_TIME = "RTCY2K_date_time"

    #-------velocity data format------------
    VELOCITY_DATA = "Velocity_data"

    #-------correlation magnitude data format------------
    CORR_MAG_DATA = "Corr_mag_data"

    #-------echo intensity data format------------
    ECHO_INTENSITY_DATA = "Echo_data"

    #-------percent good data format------------
    PERCENT_GOOD_DATA = "Percent_good_data"

    #-------status data format------------
    STATUS_DATA = "Status_data"


class ADCPT_EnsembleDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    global adcpt_cache_dict

    _data_particle_type = DataParticleType.ENSEMBLE_PARSED

    def get_byte_value(self, s, index):
        """
        Returns value of a byte (2 characters) in
        an ascii-hex string into a decimal integer
        """
        return int(s[index: index + BYTE_SIZE], 16)

    def get_word_value(self, s, index):
        """
        Returns value of a 2-byte word (4 characters) in
        an ascii-hex string into a decimal integer
        """
        upper_byte_loc = index + BYTE_SIZE
        lower_byte_loc = index
        return int(s[upper_byte_loc:upper_byte_loc + BYTE_SIZE] +
                   s[lower_byte_loc:lower_byte_loc + BYTE_SIZE], 16)

    def get_double_word_value(self, s, index):
        """
        Returns value of a 4-byte word (8 characters) in
        an ascii-hex string into a decimal integer
        """
        upper_byte_loc = index + 3 * BYTE_SIZE
        upper_middle_byte_loc = index + 2 * BYTE_SIZE
        lower_middle_byte_loc = index + BYTE_SIZE
        lower_byte_loc = index
        return int(s[upper_byte_loc:upper_byte_loc + BYTE_SIZE] +\
                   s[upper_middle_byte_loc:upper_middle_byte_loc + BYTE_SIZE] +
                   s[lower_middle_byte_loc:lower_middle_byte_loc + BYTE_SIZE] +
                   s[lower_byte_loc:lower_byte_loc + BYTE_SIZE], 16)

    def get_signed_word_value(self, s, index):
        """
        Returns value of a 2-byte word (4 characters) in
        an ascii-hex string into a decimal integer,
        but if msbit of word is '1', it is assumed to be
        a negative number, so two's complement it.
        """
        upper_byte_loc = index + BYTE_SIZE
        lower_byte_loc = index
        temp = int(s[upper_byte_loc:upper_byte_loc + BYTE_SIZE] +
                   s[lower_byte_loc:lower_byte_loc + BYTE_SIZE], 16)
        if temp > 0x7fff:
            temp ^= 0xffff
            temp *= -1
            temp -= 1
        return temp

    def get_two_byte_string(self, s, index):
        """
        Returns string of the two 2-char bytes at index (transpose the bytes,
        but leave as string value
        """
        upper_byte_loc = index + BYTE_SIZE
        lower_byte_loc = index
        return (s[upper_byte_loc:upper_byte_loc + BYTE_SIZE] +
                s[lower_byte_loc:lower_byte_loc + BYTE_SIZE])

    def calc_checksum(self, s, num_bytes):
        total = 0
        for i in range(0, num_bytes * 2, 2):
            total += self.get_byte_value(s, i)
        return hex(total)[-4:]

    # These parse_xxxx_record functions are called when one of the data types in an ensemble has been identified.
    # They return a list of dictionaries corresponding to the data in each unique data type in input 'str'.
    # 'start_index' is the index of the first location in the record, since the documentation refers to data locations
    # relative to start of record.
    # !! the relative positions of data in the records are hard-coded 'magic' number; they appear as hard-coded
    #   values because:
    #   1) dreaming up defines for each would be confusing (very easy to understand the intent of the code as written),
    #   2) the data formats are clearly documented by the manufacturer (see IOS),
    #   3) the data formats are very unlikely to change (too much manufacturer and users code would break)

    def parse_fixed_leader_record(self, s, start_index):
        global NumCells
        retlist = []
        CPU_fw_ver = self.get_byte_value(s, start_index + 4)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CPU_FW_VER,
                       DataParticleKey.VALUE: CPU_fw_ver})
        CPU_fw_rev = self.get_byte_value(s, start_index + 6)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CPU_FW_REV,
                       DataParticleKey.VALUE: CPU_fw_rev})
        SysConfig = self.get_word_value(s, start_index + 8)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SYS_CONFIG,
                       DataParticleKey.VALUE: SysConfig})
        LagLength = self.get_byte_value(s, start_index + 14)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.LAG_LEN,
                       DataParticleKey.VALUE: LagLength})
        NumBeams = self.get_byte_value(s, start_index + 16)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.NUM_BEAMS,
                       DataParticleKey.VALUE: NumBeams})
        NumCells = self.get_byte_value(s, start_index + 18)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.NUM_CELLS,
                       DataParticleKey.VALUE: NumCells})
        adcpt_cache_dict[Parameter.NUMBER_OF_DEPTH_CELLS] = NumCells
        PingsPerEnsemble = self.get_word_value(s, start_index + 20)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PINGS_PER_ENSEMBLE,
                       DataParticleKey.VALUE: PingsPerEnsemble})
        adcpt_cache_dict[Parameter.PINGS_PER_ENSEMBLE] = PingsPerEnsemble
        DepthCellLength = self.get_word_value(s, start_index + 24)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.DEPTH_CELL_LEN,
                       DataParticleKey.VALUE: DepthCellLength})
        adcpt_cache_dict[Parameter.DEPTH_CELL_SIZE] = DepthCellLength
        Blank_after_transmit = self.get_word_value(s, start_index + 28)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.BLANK_AFTER_TX,
                       DataParticleKey.VALUE: Blank_after_transmit})
        Profiling_Mode = self.get_byte_value(s, start_index + 32)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PROFILING_MODE,
                       DataParticleKey.VALUE: Profiling_Mode})
        Low_correlation_threshold = self.get_byte_value(s, start_index + 34)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.LOW_CORR_THRESH,
                       DataParticleKey.VALUE: Low_correlation_threshold})
        adcpt_cache_dict[Parameter.LOW_CORRELATION_THRESHOLD] = Low_correlation_threshold
        code_repetitions = self.get_byte_value(s, start_index + 36)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.NUM_CODE_REPS,
                       DataParticleKey.VALUE: code_repetitions})
        Percent_of_GD_minimum = self.get_byte_value(s, start_index + 38)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PERCENT_GD_MIN,
                       DataParticleKey.VALUE: Percent_of_GD_minimum})
        Error_velocity_maximum = self.get_word_value(s, start_index + 40)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ERR_VEL_MAX,
                       DataParticleKey.VALUE: Error_velocity_maximum})
        adcpt_cache_dict[Parameter.ERROR_VELOCITY_THRESHOLD] = Error_velocity_maximum
        Time_between_pings = [self.get_byte_value(s, start_index + 44),
                              self.get_byte_value(s, start_index + 46),
                              self.get_byte_value(s, start_index + 48)]
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.TIME_BETWEEN_PINGS,
                       DataParticleKey.VALUE: Time_between_pings})
        adcpt_cache_dict[Parameter.TIME_BETWEEN_PINGS] = Time_between_pings
        Coordinate_transform = self.get_byte_value(s, start_index + 50)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.COORD_XFRM,
                       DataParticleKey.VALUE: Coordinate_transform})
        Heading_alignment = self.get_word_value(s, start_index + 52)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.HEAD_ALIGN,
                       DataParticleKey.VALUE: Heading_alignment})
        Heading_bias = self.get_word_value(s, start_index + 56)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.HEAD_BIAS,
                       DataParticleKey.VALUE: Heading_bias})
        Sensor_source = self.get_byte_value(s, start_index + 60)

        bin_str = bin(Sensor_source)[2:]
        zero_fill = bin_str.zfill(8)
        assert len(zero_fill) == 8
        working_list = list(bin_str)
        working_list.reverse()

        Calc_spd_snd_from_data = False
        Use_depth_from_sensor = False
        Use_heading_from_sensor = False
        Use_pitch_from_sensor = False
        Use_roll_from_sensor = False
        Use_salinity_from_sensor = False
        Use_temperature_from_sensor = False
        if working_list[0] == '1':
            Use_temperature_from_sensor = True
        if working_list[1] == '1':
            Use_salinity_from_sensor = True
        if working_list[2] == '1':
            Use_roll_from_sensor = True
        if working_list[3] == '1':
            Use_pitch_from_sensor = True
        if working_list[4] == '1':
            Use_heading_from_sensor = True
        if working_list[5] == '1':
            Use_depth_from_sensor = True
        if working_list[6] == '1':
            Calc_spd_snd_from_data = True
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CALC_SPD_SND_FROM_DATA,
                       DataParticleKey.VALUE: Calc_spd_snd_from_data})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.USE_DEPTH_FROM_SENSOR,
                       DataParticleKey.VALUE: Use_depth_from_sensor})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.USE_HEADING_FROM_SENSOR,
                       DataParticleKey.VALUE: Use_heading_from_sensor})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.USE_PITCH_FROM_SENSOR,
                       DataParticleKey.VALUE: Use_pitch_from_sensor})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.USE_ROLL_FROM_SENSOR,
                       DataParticleKey.VALUE: Use_roll_from_sensor})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.USE_SALINITY_FROM_SENSOR,
                       DataParticleKey.VALUE: Use_salinity_from_sensor})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.USE_TEMPERATURE_FROM_SENSOR,
                       DataParticleKey.VALUE: Use_temperature_from_sensor})

        Sensor_availability = self.get_byte_value(s, start_index + 62)
        working_list = []
        bin_str = bin(Sensor_availability)[2:]
        zero_fill = bin_str.zfill(8)
        assert len(zero_fill) == 8
        working_list = list(bin_str)
        working_list.reverse()

        Depth_sensor_avail = False
        Heading_sensor_avail = False
        Pitch_sensor_avail = False
        Roll_sensor_avail = False
        Salinity_sensor_avail = False
        Temperature_sensor_avail = False

        if working_list[0] == '1':
            Temperature_sensor_avail = True
        if working_list[1] == '1':
            Salinity_sensor_avail = True
        if working_list[2] == '1':
            Roll_sensor_avail = True
        if working_list[3] == '1':
            Pitch_sensor_avail = True
        if working_list[4] == '1':
            Heading_sensor_avail = True
        if working_list[5] == '1':
            Depth_sensor_avail = True
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.DEPTH_SENSOR_AVAIL,
                       DataParticleKey.VALUE: Depth_sensor_avail})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.HEADING_SENSOR_AVAIL,
                       DataParticleKey.VALUE: Heading_sensor_avail})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PITCH_SENSOR_AVAIL,
                       DataParticleKey.VALUE: Pitch_sensor_avail})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ROLL_SENSOR_AVAIL,
                       DataParticleKey.VALUE: Roll_sensor_avail})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SALINITY_SENSOR_AVAIL,
                       DataParticleKey.VALUE: Salinity_sensor_avail})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.TEMPERATURE_SENSOR_AVAIL,
                       DataParticleKey.VALUE: Temperature_sensor_avail})

        Distance_to_bin_1 = self.get_word_value(s, start_index + 64)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.BIN1_DIST,
                       DataParticleKey.VALUE: Distance_to_bin_1})
        Xmit_Pulse_Length = self.get_word_value(s, start_index + 68)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.XMIT_PULSE_LEN,
                       DataParticleKey.VALUE: Xmit_Pulse_Length})
        WP_ref_layer_avg = self.get_word_value(s, start_index + 72)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.WP_REF_LAYER_AVG,
                       DataParticleKey.VALUE: WP_ref_layer_avg})
        False_Target_Threshold = self.get_word_value(s, start_index + 76)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.FALSE_TARGET_THRESH,
                       DataParticleKey.VALUE: False_Target_Threshold})
        Transmit_Lag_Distance = self.get_word_value(s, start_index + 80)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.XMIT_LAG_DIST,
                       DataParticleKey.VALUE: Transmit_Lag_Distance})
        ### CPU serial number merely reported as raw string; not clear from documentation how to decode it.
        CPU_board_serial_number = s[start_index + 84:start_index+100]
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CPU_SN,
                       DataParticleKey.VALUE: CPU_board_serial_number})
        System_Bandwidth = self.get_word_value(s, start_index + 100)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SYS_BW,
                       DataParticleKey.VALUE: System_Bandwidth})
        System_Power = self.get_byte_value(s, start_index + 104)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SYS_PWR,
                       DataParticleKey.VALUE: System_Power})
        adcpt_cache_dict[Parameter.TRANSMIT_POWER] = System_Power
        ###### Instrument serial number merely reported as raw string; not clear from documentation how to decode it.
        Instrument_Serial_Number = s[start_index + 108:start_index + 116]
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.INST_SN,
                       DataParticleKey.VALUE: Instrument_Serial_Number})
        Beam_Angle = self.get_byte_value(s, start_index + 116)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.BEAM_ANGLE,
                       DataParticleKey.VALUE: Beam_Angle})
        return retlist

    def parse_var_leader_record(self, s, start_index):
        retlist = []
        Ensemble_Number = self.get_word_value(s, start_index + 4)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ENSEMBLE_NUMBER,
                       DataParticleKey.VALUE: Ensemble_Number})
        RTC_date_time = [self.get_byte_value(s, start_index + 8),
                         self.get_byte_value(s, start_index + 10),
                         self.get_byte_value(s, start_index + 12),
                         self.get_byte_value(s, start_index + 14),
                         self.get_byte_value(s, start_index + 16),
                         self.get_byte_value(s, start_index + 18),
                         self.get_byte_value(s, start_index + 20)]
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.RTC_DATE_TIME,
                       DataParticleKey.VALUE: RTC_date_time})
        # Create a timestamp in ntp format
        struct_time = RTC_date_time[:6]
        hundredths = float(RTC_date_time[6]) / 100
        struct_time.extend([0, 0, -1])
        timestamp = ntplib.system_to_ntp_time(time.mktime(struct_time)) + hundredths
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.TIMESTAMP,
                       DataParticleKey.VALUE: timestamp})
        Ensemble_number_msb = self.get_byte_value(s, start_index + 22)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ENSEMBLE_NUM_MSB,
                       DataParticleKey.VALUE: Ensemble_number_msb})
        Built_in_Test_Results = self.get_word_value(s, start_index + 24)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.BIT_RESULT,
                       DataParticleKey.VALUE: Built_in_Test_Results})
        Speed_of_sound = self.get_word_value(s, start_index + 28)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SPEED_OF_SOUND,
                       DataParticleKey.VALUE: Speed_of_sound})
        adcpt_cache_dict[Parameter.SPEED_OF_SOUND] = Speed_of_sound
        Depth_of_transducer = self.get_word_value(s, start_index + 32)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.DEPTH_OF_XDUCER,
                       DataParticleKey.VALUE: Depth_of_transducer})
        Heading = self.get_byte_value(s, start_index + 36)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.HEADING,
                       DataParticleKey.VALUE: Heading})
        Pitch = self.get_word_value(s, start_index + 40)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PITCH,
                       DataParticleKey.VALUE: Pitch})
        Roll = self.get_word_value(s, start_index + 44)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ROLL,
                       DataParticleKey.VALUE: Roll})
        Salinity = self.get_word_value(s, start_index + 48)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SALINITY,
                       DataParticleKey.VALUE: Salinity})
        adcpt_cache_dict[Parameter.SALINITY] = Salinity
        Temperature = self.get_word_value(s, start_index + 52)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.TEMPERATURE,
                       DataParticleKey.VALUE: Temperature})
        Min_pre_ping_wait_time = [self.get_byte_value(s, start_index + 56),
                                  self.get_byte_value(s, start_index + 58),
                                  self.get_byte_value(s, start_index + 60)]
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.MIN_PRE_PING_WAIT_TIME,
                       DataParticleKey.VALUE: Min_pre_ping_wait_time})
        Heading_deviation = self.get_byte_value(s, start_index + 62)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.HDG_DEV,
                       DataParticleKey.VALUE: Heading_deviation})
        Pitch_deviation = self.get_byte_value(s, start_index + 64)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PITCH_DEV,
                       DataParticleKey.VALUE: Pitch_deviation})
        Roll_deviation = self.get_byte_value(s, start_index + 66)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ROLL_DEV,
                       DataParticleKey.VALUE: Roll_deviation})
        Xmit_current = self.get_byte_value(s, start_index + 68)
        Xmit_voltage = self.get_byte_value(s, start_index + 70)
        Ambient_temp = self.get_byte_value(s, start_index + 72)
        Pressure_pos = self.get_byte_value(s, start_index + 74)
        Pressure_neg = self.get_byte_value(s, start_index + 76)
        Attitude_temp = self.get_byte_value(s, start_index + 78)
        Attitude = self.get_byte_value(s, start_index + 80)
        Contamination_sensor = self.get_byte_value(s, start_index + 82)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.XMIT_CURRENT,
                       DataParticleKey.VALUE: Xmit_current})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.XMIT_VOLTAGE,
                       DataParticleKey.VALUE: Xmit_voltage})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.AMBIENT_TEMP,
                       DataParticleKey.VALUE: Ambient_temp})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PRESSURE_POS,
                       DataParticleKey.VALUE: Pressure_pos})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PRESSURE_NEG,
                       DataParticleKey.VALUE: Pressure_neg})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ATTITUDE_TEMP,
                       DataParticleKey.VALUE: Attitude_temp})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ATTITUDE,
                       DataParticleKey.VALUE: Attitude})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CONTAMINATION_SENSOR,
                       DataParticleKey.VALUE: Contamination_sensor})
        status_word = self.get_double_word_value(s, start_index + 84)

        bin_str = bin(status_word)[2:]
        zero_fill = bin_str.zfill(32)
        assert len(zero_fill) == 32
        working_list = list(zero_fill)
        working_list.reverse()

        Bus_error = False
        Address_error = False
        Illegal_instruction = False
        Divide_by_zero = False
        Emulator_exception = False
        Unassigned_exception = False
        Watchdog = False
        Battery_save_power = False
        Pinging = False
        Cold_wakeup = False
        Unknown_wakeup = False
        Clock_read_error = False
        Unexpected_alarm = False
        Clock_jump_forward = False
        Clock_jump_backward = False
        Power_fail = False
        Spurious_4_interrupt = False
        Spurious_5_interrupt = False
        Spurious_6_interrupt = False
        Level_7_interrupt = False

        if working_list[0] == '1':
            Bus_error = True
        if working_list[1] == '1':
            Address_error = True
        if working_list[2] == '1':
            Illegal_instruction = True
        if working_list[3] == '1':
            Divide_by_zero = True
        if working_list[4] == '1':
            Emulator_exception = True
        if working_list[5] == '1':
            Unassigned_exception = True
        if working_list[6] == '1':
            Watchdog = True
        if working_list[7] == '1':
            Battery_save_power = True
        if working_list[8] == '1':
            Pinging = True
        if working_list[14] == '1':
            Cold_wakeup = True
        if working_list[15] == '1':
            Unknown_wakeup = True
        if working_list[16] == '1':
            Clock_read_error = True
        if working_list[17] == '1':
            Unexpected_alarm = True
        if working_list[18] == '1':
            Clock_jump_forward = True
        if working_list[19] == '1':
            Clock_jump_backward = True
        if working_list[27] == '1':
            Power_fail = True
        if working_list[28] == '1':
            Spurious_4_interrupt = True
        if working_list[29] == '1':
            Spurious_5_interrupt = True
        if working_list[30] == '1':
            Spurious_6_interrupt = True
        if working_list[31] == '1':
            Level_7_interrupt = True
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.BUS_ERR,
                       DataParticleKey.VALUE: Bus_error})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ADDR_ERR,
                       DataParticleKey.VALUE: Address_error})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ILLEGAL_INSTR,
                       DataParticleKey.VALUE: Illegal_instruction})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ZERO_DIV,
                       DataParticleKey.VALUE: Divide_by_zero})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.EMUL_EXCEP,
                       DataParticleKey.VALUE: Emulator_exception})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.UNASS_EXCEP,
                       DataParticleKey.VALUE: Unassigned_exception})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.WATCHDOG,
                       DataParticleKey.VALUE: Watchdog})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.BATT_SAVE_PWR,
                       DataParticleKey.VALUE: Battery_save_power})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PINGING,
                       DataParticleKey.VALUE: Pinging})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.COLD_WAKEUP,
                       DataParticleKey.VALUE: Cold_wakeup})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.UNKNOWN_WAKEUP,
                       DataParticleKey.VALUE: Unknown_wakeup})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CLOCK_RD_ERR,
                       DataParticleKey.VALUE: Clock_read_error})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.UNEXP_ALARM,
                       DataParticleKey.VALUE: Unexpected_alarm})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CLOCK_JMP_FWD,
                       DataParticleKey.VALUE: Clock_jump_forward})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CLOCK_JMP_BKWRD,
                       DataParticleKey.VALUE: Clock_jump_backward})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PWR_FAIL,
                       DataParticleKey.VALUE: Power_fail})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SPUR_4_INTR,
                       DataParticleKey.VALUE: Spurious_4_interrupt})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SPUR_5_INTR,
                       DataParticleKey.VALUE: Spurious_5_interrupt})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SPUR_6_INTR,
                       DataParticleKey.VALUE: Spurious_6_interrupt})
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.LEV_7_INTR,
                       DataParticleKey.VALUE: Level_7_interrupt})
        Pressure = self.get_double_word_value(s, start_index + 96)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PRESSURE,
                       DataParticleKey.VALUE: Pressure})
        Pressure_sensor_variance = self.get_double_word_value(s, start_index + 104)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PRESSURE_VAR,
                       DataParticleKey.VALUE: Pressure_sensor_variance})
        RTCY2K_date_time = [self.get_byte_value(s, start_index + 114), self.get_byte_value(s, start_index + 116),
                            self.get_byte_value(s, start_index + 118), self.get_byte_value(s, start_index + 120),
                            self.get_byte_value(s, start_index + 122), self.get_byte_value(s, start_index + 124),
                            self.get_byte_value(s, start_index + 126), self.get_byte_value(s, start_index + 128)]
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.RTCY2K_DATE_TIME,
                       DataParticleKey.VALUE: RTCY2K_date_time})
        return retlist

    def parse_velocity_record(self, s, start_index):
        SIZE_OF_CELL_DATA = 16
        templist = []
        local_index = 4   # starting location in header
        for cell_count in range(0, NumCells):
            vel_list = [self.get_signed_word_value(s, start_index + local_index),
                        self.get_signed_word_value(s, start_index + local_index + 4),
                        self.get_signed_word_value(s, start_index + local_index + 8),
                        self.get_signed_word_value(s, start_index + local_index + 12)]
            templist.append(vel_list)
            local_index += SIZE_OF_CELL_DATA
        return templist

    def parse_bottom_track_record(self, s, start_index):
        pass

    def parse_data_record(self, s, start_index):
        SIZE_OF_CELL_DATA = 8
        templist = []
        local_index = 4  # starting location in header
        for cell_count in range(0, NumCells):
            vel_list = [self.get_byte_value(s, start_index + local_index),
                         self.get_byte_value(s, start_index + local_index + 2),
                         self.get_byte_value(s, start_index + local_index + 4),
                         self.get_byte_value(s, start_index + local_index + 6)]
            templist.append(vel_list)
            local_index += SIZE_OF_CELL_DATA
        return templist

    def _build_parsed_values(self):
        """
        Take something in the autosample format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """
        global num_data_types, num_bytes_in_ensemble
        log.debug("in ADCPT_HeaderSampleDataParticle._build_parsed_values")
        # initialize
        num_data_types = None
        num_bytes_in_ensemble = None

        data_stream = self.raw_data
        num_data_types = self.get_byte_value(data_stream, NUM_DATA_TYPES_INDEX)
        num_bytes_in_ensemble = self.get_word_value(data_stream, NUM_BYTES_IN_ENSEMBLE_INDEX)
        result = [{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.NUM_DATA_TYPES,
                   DataParticleKey.VALUE: num_data_types},
                  {DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.NUM_BYTES_IN_ENSEMBLE,
                  DataParticleKey.VALUE: num_bytes_in_ensemble}]

        # calculate checksum over entire ensemble and compare the value
        # to the checksum attached to end of ensemble.
        # assert error if not equal
        num_chars = num_bytes_in_ensemble * 2
        try:
            assert self.calc_checksum(data_stream, num_bytes_in_ensemble) == \
                  data_stream[num_chars + 2: num_chars + 4] + \
                  data_stream[num_chars: num_chars + 2], \
                  'Checksum error in reading ensemble'
        except AssertionError, args:
            log.error("In build_parsed_values; %s" % str(args))

        # Now look at data in data_types records; use data type 
        # offset to point to start of records
        # Use 2-byte IDs in each record to identify type of data record
        # (The only items in an ensemble that exist at fixed offsets 
        # are num_data_types, num_bytes_in_ensemble,
        # and the offsets of the data type records.
        # Now build a list of data type records
        for type_cnt in range(0, num_data_types):
            id_offset_addr = type_cnt * WORD_SIZE + DATA_TYPE_LOC_INDEX_BASE
            id_offset = BYTE_SIZE * self.get_word_value(data_stream, id_offset_addr)
            id_value = data_stream[id_offset:id_offset + WORD_SIZE]
            if id_value == FIXED_LEADER_ID:
                result.extend(self.parse_fixed_leader_record(data_stream, id_offset))
            elif id_value == VAR_LEADER_ID:
                result.extend(self.parse_var_leader_record(data_stream, id_offset))
            elif id_value == VELOCITY_ID:
                result.extend([{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.VELOCITY_DATA,
                   DataParticleKey.VALUE: self.parse_velocity_record(data_stream, id_offset)}])
            elif id_value == CORR_MAG_ID:
                result.extend([{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CORR_MAG_DATA,
                   DataParticleKey.VALUE: self.parse_data_record(data_stream, id_offset)}])
            elif id_value == ECHO_INTENSITY_ID:
                result.extend([{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ECHO_INTENSITY_DATA,
                   DataParticleKey.VALUE: self.parse_data_record(data_stream, id_offset)}])
            elif id_value == PERCENT_GOOD_ID:
                result.extend([{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PERCENT_GOOD_DATA,
                   DataParticleKey.VALUE: self.parse_data_record(data_stream, id_offset)}])
            elif id_value == STATUS_ID:
                result.extend([{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.STATUS_DATA,
                   DataParticleKey.VALUE: self.parse_data_record(data_stream, id_offset)}])
            elif id_value == PERCENT_GOOD_ID:
                result.extend([{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PERCENT_GOOD_DATA,
                   DataParticleKey.VALUE: self.parse_data_record(data_stream, id_offset)}])
            else:
                log.error("Data type record ID %s not recognized in build_parsed_values" % id_value)
        log.debug("after parsing ensemble, adcpt_cache_dict is %s" % adcpt_cache_dict)        
        return result


###############################################################################
# Driver
###############################################################################
class InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    def __init__(self, evt_callback):
        """
        Driver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    ########################################################################
    # Protocol builder.
    ########################################################################
    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################
class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """
    global adcpt_cache_dict

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build ADCPT protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.BREAK_SUCCESS, self._handler_unknown_break_success)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.BREAK_ALARM, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET,  self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET,  self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.QUIT_SESSION, self._handler_command_quit_session)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.POWERING_DOWN, self._handler_command_powering_down)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SELF_DEPLOY, self._handler_command_self_deploy)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.BREAK_SUCCESS, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET,  self._handler_autosample_get)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        ### -- first the action commands
        self._add_build_handler(InstrumentCmds.POWER_DOWN, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.START_DEPLOYMENT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SAVE_SETUP_TO_RAM, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SEND_LAST_DATA_ENSEMBLE, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_ERROR_STATUS_WORD, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.CLEAR_ERROR_STATUS_WORD, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_SYSTEM_CONFIGURATION, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_TRANSFORMATION_MATRIX, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_FAULT_LOG, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.CLEAR_FAULT_LOG, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.BUILT_IN_TEST, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.OUTPUT_CALIBRATION_DATA, self._build_simple_command)

        ### -- then the default commands (usually startup commands)
        self._add_build_handler(InstrumentCmds.COMM_PARAMS_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.COLLECTION_MODE_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SPEED_OF_SOUND_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.INSTRUMENT_ID_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SALINITY_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.TIME_PER_BURST_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.ENSEMBLES_PER_BURST_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.TIME_PER_ENSEMBLE_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.TIME_OF_FIRST_PING_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.TIME_OF_FIRST_PING_Y2K_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.TIME_BETWEEN_PINGS_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.REAL_TIME_CLOCK_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.REAL_TIME_CLOCK_Y2K_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.BUFFERED_OUTPUT_PERIOD_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.NUMBER_OF_DEPTH_CELLS_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.PINGS_PER_ENSEMBLE_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DEPTH_CELL_SIZE_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.TRANSMIT_LENGTH_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.PING_WEIGHT_DEFAULT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.AMBIGUITY_VELOCITY_DEFAULT, self._build_simple_command)

        ### -- and finally the SET commands
        self._add_build_handler(InstrumentCmds.SET_TRANSMIT_POWER, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_SPEED_OF_SOUND, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_SALINITY, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_TIME_PER_BURST, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_ENSEMBLES_PER_BURST, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_TIME_PER_ENSEMBLE, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_TIME_OF_FIRST_PING, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_TIME_OF_FIRST_PING_Y2K, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_TIME_BETWEEN_PINGS, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_REAL_TIME_CLOCK, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_REAL_TIME_CLOCK_Y2K, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_BUFFERED_OUTPUT_PERIOD, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_FALSE_TARGET_THRESHOLD_MAXIMUM, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_LOW_CORRELATION_THRESHOLD, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_ERROR_VELOCITY_THRESHOLD, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_CLIP_DATA_PAST_BOTTOM, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_RECEIVER_GAIN_SELECT, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_WATER_REFERENCE_LAYER, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_NUMBER_OF_DEPTH_CELLS, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_PINGS_PER_ENSEMBLE, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_DEPTH_CELL_SIZE, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_TRANSMIT_LENGTH, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_PING_WEIGHT, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_AMBIGUITY_VELOCITY, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_MODE_1_BANDWIDTH_CONTROL, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_BLANK_AFTER_TRANSMIT, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_DATA_OUT, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_INSTRUMENT_ID, self._build_set_command)
        self._add_build_handler(InstrumentCmds.SET_WATER_PROFILING_MODE, self._build_set_command)

        # Add response handlers for device commands.
        #  self._add_response_handler(InstrumentCmds.DISPLAY_SYSTEM_CONFIGURATION, self._parse_display_system_configuration_response)
        #  self._add_response_handler(InstrumentCmds.DISPLAY_TRANSFORMATION_MATRIX, self._parse_display_transformation_matrix_response)
        #  self._add_response_handler(InstrumentCmds.DISPLAY_FAULT_LOG, self._parse_display_fault_log_response)
        #  self._add_response_handler(InstrumentCmds.BUILT_IN_TEST, self._parse_built_in_test_response)
        #  self._add_response_handler(InstrumentCmds.OUTPUT_CALIBRATION_DATA, self._parse_output_calibration_data_response)

        self._add_response_handler(InstrumentCmds.DISPLAY_SYSTEM_CONFIGURATION, self._build_simple_command)
        self._add_response_handler(InstrumentCmds.DISPLAY_TRANSFORMATION_MATRIX, self._build_simple_command)
        self._add_response_handler(InstrumentCmds.DISPLAY_FAULT_LOG, self._build_simple_command)
        self._add_response_handler(InstrumentCmds.BUILT_IN_TEST, self._build_simple_command)
        self._add_response_handler(InstrumentCmds.OUTPUT_CALIBRATION_DATA, self._build_simple_command)

        # Add sample handlers.

        # Start state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

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
        The method that splits samples
        Chunker sieve method to help the chunker identify chunks.
        @returns a list of chunks identified, if any. 
        The chunks are all the same type.
        """

        raw_data = raw_data.replace('\xef', '?')

        sieve_matchers = [ENSEMBLE_REGEX_MATCHER,
                          CALIBRATION_DATA_REGEX_MATCHER,
                          PS0_REGEX_MATCHER,
                          PS3_REGEX_MATCHER,
                          FD_REGEX_MATCHER,
                          PT200_REGEX_MATCHER,
                          BREAK_SUCCESS_REGEX,
                          BREAK_ALARM_REGEX,
                          POWERING_DOWN_REGEX,
                          ERR_REGEX]

        return_list = []
        for matcher in sieve_matchers:
            if matcher == ENSEMBLE_REGEX_MATCHER:
                start_pos = 0   # starting index in a string for search
                numIDs = raw_data.count(ENSEMBLE_HEADER_ID)    # see how many ensembles to look for
                while numIDs > 0:
                    pos = raw_data.find(ENSEMBLE_HEADER_ID, start_pos)
                    strip = raw_data[pos:]

                    if len(strip) > ENSEMBLE_LENGTH_LOC + WORD_SIZE:  # make sure you have long-enough string to get the ensemble size
                        ensemble_length_bytes = int(strip[ENSEMBLE_LENGTH_LOC + 2: ENSEMBLE_LENGTH_LOC + 4] + 
                                                    strip[ENSEMBLE_LENGTH_LOC: ENSEMBLE_LENGTH_LOC + 2], 16)
                        ensemble_length_chars = BYTE_SIZE * ensemble_length_bytes + WORD_SIZE  # size in header didn't include size of checksum word
                        if len(strip) >= ensemble_length_chars:
                            log.debug("sieve_function got enough data")
                            return_list.append((pos, pos + ensemble_length_chars))
                            start_pos += pos + ensemble_length_chars
                        else:
                            log.debug("sieve_function didn't get enough data")
                    numIDs -= 1

            elif matcher == BREAK_SUCCESS_REGEX:
                ### This should not be done in the sieve. Steve F. suggets using command
                ### responses where possible, and monitoring _linebuf() if no command is
                ### involved.
                ### THIS ONE WILL BE A RESPONSE TO A BREAK COMMAND; STILL UNCLEAR HOW TO
                ### ISSUE IT.
                pass
            elif matcher == BREAK_ALARM_REGEX:
                ### This should not be done in the sieve. Steve F. suggets using command
                ### responses where possible, and monitoring _linebuf() if no command is
                ### involved.
                ### THIS ONE WILL BE A RESPONSE TO A BREAK COMMAND; STILL UNCLEAR HOW TO
                ### ISSUE IT.
                pass
            elif matcher == POWERING_DOWN_REGEX:
                ### This should not be done in the sieve. Steve F. suggets using command
                ### responses where possible, and monitoring _linebuf() if no command is
                ### involved.
                ### THIS ONE OCCURS ASYNCHRONOUSLY. THERE IS ALSO A MESSAGE ABOUT REVERTING
                ### TO DEPLOYED STATE, ALSO ASYNCHRONOUS.  ???
                pass
            elif matcher == ERR_REGEX:
                ### This should not be done in the sieve. Steve F. suggets using command
                ### responses where possible, and monitoring _linebuf() if no command is
                ### involved.
                ### THIS ONE IS DEFINITELY A RESPONSE MESSAGE!
                pass
            else:
                for match in matcher.finditer(raw_data):
                    return_list.append((match.start(), match.end()))

        return return_list

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with sbe26plus parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """

        self._param_dict.add(Parameter.INSTRUMENT_ID,
            r'CI = (\d+) \-+ Instrument ID \(0-255\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.POLLED_MODE,
            r'CP = (\d) \-+ PolledMode \(1=ON, 0=OFF;  BREAK resets\)',
            lambda match: bool(match.group(1)),
            self._bool_to_int)

        self._param_dict.add(Parameter.XMIT_POWER,
            r'CQ = (\d+) \-+ Xmt Power \(0=Low, 255=High\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.TIME_PER_BURST,
            r'TC (\d+) \-+ Ensembles Per Burst \(0\-65535\)',
            lambda match: datetime.strptime(match.group(1), '%H:%M:%S.%f'),
            self._datetime_with_milis_to_time_string_with_milis)

        self._param_dict.add(Parameter.ENSEMBLES_PER_BURST,
            r'TC (\d+) \-+ Ensembles Per Burst \(0\-65535\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.TIME_PER_ENSEMBLE,
            r'TE (\d\d:\d\d:\d\d.\d\d \-+ Time per Ensemble \(hrs:min:sec.sec/100\)',
            lambda match: str(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.TIME_OF_FIRST_PING,
            r'TF (../../..,..:..:..) --- Time of First Ping \(yr/mon/day,hour:min:sec\)',
            lambda match: str(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.TIME_OF_FIRST_PING_Y2K,
            r'TG (..../../..,..:..:..) - Time of First Ping \(CCYY/MM/DD,hh:mm:ss\)',
            lambda match: str(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.TIME_PER_PING,
            r'TP (\d\d:\d\d.\d\d) \-+ Time per Ping \(min:sec.sec/100\)',
            lambda match: str(match.group(1)),
            self._string_to_string)

        #self._param_dict.add(Parameter.TIME,
        #    r'TS (\d\d/\d\d/\d\d,\d\d:\d\d:\d\d) \-+ Time Set \(yr/mon/day,hour:min:sec\)',
        #    lambda match: time.strptime(match.group(1), "%y/%m/%d,%H:%M:%S"),
        #    self._datetime_YY_to_string)

        self._param_dict.add(Parameter.TIME,
            r'TT (\d\d\d\d/\d\d/\d\d,\d\d:\d\d:\d\d) \- Time Set \(CCYY/MM/DD,hh:mm:ss\)',
            lambda match: time.strptime(match.group(1), "%Y/%m/%d,%H:%M:%S"),
            self._datetime_YYYY_to_string)

        self._param_dict.add(Parameter.BUFFERED_OUTPUT_PERIOD,
            r'TX (\d\d:\d\d:\d\d) \-+ Buffer Output Period: \(hh:mm:ss\)',
            lambda match: time.strptime(match.group(1), "%H:%M:%S"),
            self._time_to_string)

        self._param_dict.add(Parameter.FALSE_TARGET_THRESHOLD,
            r'WA (\d+,\d+) \-+ False Target Threshold \(Max\)\(0-255\),\[Start Bin\]',
            lambda match: str(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.CORRELATION_THRESHOLD,
            r'WC (\d+) \-+ Correlation Threshold',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.SERIAL_OUT_FW_SWITCHES,
            r'WD (\d+) \-+ Data Out \(Vel;Cor;Amp  PG;St;P0  P1;P2;P3\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.ERROR_VELOCITY_THRESHOLD,
            r'WE (\d+) \-+ Error Velocity Threshold \(0\-5000 mm/s\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.BLANK_AFTER_TRANSMIT,
            r'WF (\d+) \-+ Blank After Transmit \(cm\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.CLIP_DATA_PAST_BOTTOM,
            r'WI (\d) \-+ Clip Data Past Bottom \(0=OFF,1=ON\)',
            lambda match: bool(match.group(1)),
            self._bool_to_int)

        self._param_dict.add(Parameter.RECEIVER_GAIN_SELECT,
            r'WJ (\d) \-+ Rcvr Gain Select \(0=Low,1=High\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.WATER_REFERENCE_LAYER,
            r'WL (\d+,\d+) \-+ Water Reference Layer:  Begin Cell \(0=OFF\), End Cell',
            lambda match: str(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.WATER_PROFILING_MODE,
            r'WM (\d+) \-+ Profiling Mode \(1\-15\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.NUMBER_OF_DEPTH_CELLS,
            r'WN (\d+) \-+ Number of depth cells \(1\-255\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.PINGS_PER_ENSEMBLE,
            r'WP (\d+) \-+ Pings per Ensemble \(0\-16384\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.DEPTH_CELL_SIZE,
            r'WS (\d+) \-+ Depth Cell Size \(cm\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.TRANSMIT_LENGTH,
            r'WT (\d+) \-+ Transmit Length (cm) \[0 = Bin Length\]',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.PING_WEIGHT,
            r'WU (\d) \-+ Ping Weighting \(0=Box,1=Triangle\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.AMBIGUITY_VELOCITY,
            r'WV (\d) \-+ Mode 1 Ambiguity Vel \(cm/s radial\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.CHOOSE_EXTERNAL_DEVICE,
            r'CC = (\d\d\d \d\d\d \d\d\d) \-+ Choose External Devices \(x;x;x  x;x;x  x;x;SBMC\)',
            lambda match: str(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.BANNER,
            r'CH = (\d) \-+ Suppress Banner',
            lambda match: not bool(match.group(1)),
            self._reverse_bool_to_int)

        self._param_dict.add(Parameter.IMM_OUTPUT_ENABLE,
            r'CJ = (\d) \-+ IMM Output Enable \(0=Disable,1=Enable\)',
            lambda match: bool(match.group(1)),
            self._bool_to_int)

        self._param_dict.add(Parameter.SLEEP_ENABLE,
            r'CL = (\d) \-+ Sleep Enable \(0 = Disable, 1 = Enable, 2 See Manual\)',
            lambda match: bool(match.group(1)),
            self._bool_to_int)

        self._param_dict.add(Parameter.SERIAL_SYNC_MASTER,
            r'CM = (\d) \-+ RS-232 Sync Master \(0 = OFF, 1 = ON\)',
            lambda match: bool(match.group(1)),
            self._bool_to_int)

        self._param_dict.add(Parameter.SAVE_NVRAM_TO_RECORDER,
            r'CN = (\d) \-+ Save NVRAM to recorder \(0 = ON, 1 = OFF\)',
            lambda match: bool(match.group(1)),
            self._bool_to_int)

        self._param_dict.add(Parameter.TRIGGER_TIMEOUT,
            r'CW = (\d+) \-+ Trigger Timeout \(ms; 0 = no timeout\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.LOW_LATENCY_TRIGGER_ENABLE,
            r'CX = (\d) \-+ Trigger Enable \(0 = OFF, 1 = ON\)',
            lambda match: bool(match.group(1)),
            self._bool_to_int)

        self._param_dict.add(Parameter.HEADING_ALIGNMENT,
            r'EA = ([\+\-\d]+) \-+ Heading Alignment \(1/100 deg\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.HEADING_BIAS,
            r'EB = ([\+\-\d]+) \-+ Heading Bias \(1/100 deg\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.SPEED_OF_SOUND,
            r'EC = (\d+) \-+ Speed Of Sound \(m/s\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.TRANSDUCER_DEPTH,
            r'ED = (\d+) \-+ Transducer Depth \(0 \- 65535 dm\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.HEADING,
            r'EH = (\d+) \-+ Heading \(1/100 deg\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.PITCH,
            r'EP = ([\+\-\d]+) \-+ Tilt 1 Sensor \(1/100 deg\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.ROLL,
            r'ER = ([\+\-\d]+) \-+ Tilt 2 Sensor \(1/100 deg\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.SALINITY,
            r'ES = (\d+) \-+ Salinity \(0-40 pp thousand\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.TEMPERATURE,
            r'ET = ([\+\-\d]+) \-+ Temperature \(1/100 deg Celsius\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.COORDINATE_TRANSFORMATION,
            r'EX = (\d+) \-+ Coord Transform \(Xform:Type; Tilts; 3Bm; Map\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.SENSOR_SOURCE,
            r'EZ = (\d) \-+ Sensor Source \(C;D;H;P;R;S;T\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.OUTPUT_BIN_SELECTION,
            r'PB = ([\d,]+) \-+ PD12 Bin Select \(first;num;sub\)',
            lambda match: str(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.DATA_STREAM_SELECT,
            r'PD = (\d+) \-+ Data Stream Select \(0\-18\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.ENSEMBLE_SELECT,
            r'PE = (\d+) \-+ PD12 Ensemble Select \(1\-65535\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.VELOCITY_COMPONENT_SELECT,
            r'PO = (\d) \-+ PD12 Velocity Component Select \(v1;v2;v3;v4\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.SYNCHRONIZE,
            r'SA = (\d+) \-+ Synch Before/After Ping/Ensemble Bottom/Water/Both',
            lambda match: int(match.group(1)),
            self._int_to_string)

        #
        # This may enable resume after timeout...
        #
        self._param_dict.add(Parameter.BREAK_INTERUPTS,
            r'SB = (\d) \-+ Channel B Break Interrupts are ENABLED',
            lambda match: bool(match.group(1)),
            self._bool_to_int)

        self._param_dict.add(Parameter.SYNC_INTERVAL,
            r'SI = (\d+) \-+ Synch Interval \(0\-65535\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.MODE_SELECT,
            r'SM = (\d+) \-+ Mode Select \(0=OFF,1=MASTER,2=SLAVE,3=NEMO\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.RDS3_SLEEP_MODE,
            r'SS = (\d+) \-+ RDS3 Sleep Mode \(0=No Sleep\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.SLAVE_TIMEOUT,
            r'ST = (\d+) \-+ Slave Timeout \(seconds,0=indefinite\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.SYNC_DELAY,
            r'SW = (\d+) \-+ Synch Delay (1/10 msec)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.DEVICE_485_ID,
            r'DW  (\d+) \-+ Current ID on RS\-485 Bus',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.DEPLOYMENT_AUTO_INCRIMENT,
            r'Deployment Auto Increment is (.*)',
            lambda match: True if (match.group(1) =='ENABLED') else False,
            self._bool_to_int)

        self._param_dict.add(Parameter.DEPLOYMENT_NAME,
            r'Current deployment name = (.*)',
            lambda match: str(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.BANDWIDTH_CONTROL,
            r'WB 1 \-+ Bandwidth Control \(0=Wid,1=Nar\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.WANTED_GOOD_PERCENT,
            r'WG (\d) \-+ Percent Good Minimum \(1\-100\%\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.SAMPLE_AMBIENT_SOUND,
            r'WQ (\d) \-+ Sample Ambient Sound \(0=OFF,1=ON\)',
            lambda match: bool(match.group(1)),
            self._bool_to_int)

        self._param_dict.add(Parameter.PINGS_BEFORE_REAQUIRE,
            r'WW (\d+) \-+ Mode 1 Pings before Mode 4 Re\-acquire',
            lambda match: int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.MODE_5_AMBIGUITY_VELOCITY,
            r'WZ (\d+) \-+ Mode 5 Ambiguity Velocity \(cm/s radial\)',
            lambda match: int(match.group(1)),
            self._int_to_string)

        #
        # Read Only Vars
        #

        """
        >>> import re
        >>> t = "RA?\r\n\r\n0\r\n"
        >>> pat = re.compile(r'RA\?\r\n\r\n([\d\.]+)\r\n'
        ... )
        >>> pat.match(t)
        <_sre.SRE_Match object at 0x109d203f0>
        >>> m = pat.match(t)
        >>> m.group(1)
        '0'
        """
        #ZERO_PRESSURE_READING = 'AZ'        #  Zero pressure reading' (RO) ALSO a command
        self._param_dict.add(Parameter.ZERO_PRESSURE_READING,
            r'AZ\?\n\r\n\r([\d\.]+)\n\r',
            lambda match: float(match.group(1)),
            self._float_to_string,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.SERIAL_PORT_CONTROL,
            r'CB = (\d\d\d) \-+ Serial Port Control \(Baud [4=9600]; Par; Stop\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.SERIAL_DATA_OUT,
            r'CD = (\d\d\d \d\d\d \d\d\d) \-+ Serial Data Out \(Vel;Cor;Amp  PG;St;P0  P1;P2;P3\)',
            lambda match: str(match.group(1)),
            self._string_to_string,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.SERIAL_FLOW_CONTROL,
            r'CF = (\d+) \-+ Flow Ctrl \(EnsCyc;PngCyc;Binry;Ser;Rec\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.SERIAL_485_BAUD,
            r'DB (\d+) \-+ RS-485 Port Control \(Baud; N/U; N/U\)',
            lambda match: int(match.group(1)),
            self._int_to_string,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.DEPLOYMENTS_RECORDED,
            r'AZ\?\n\r\n\r([\d\.]+)\n\r',
            lambda match: int(match.group(1)),
            self._int_to_string,
            visibility=ParameterDictVisibility.READ_ONLY)

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Send a CE (send last data ensemble)
        command to the adcpt; this causes the chunker to extract last data
        and put in adcpt_cache_dict.  Then calling _build_param_dict() causes
        the new data to be updated in param dict.
        """
        # Get old param dict config.
        old_config = self._param_dict.get_config()

        # Issue display commands and parse results.

        ### adcpt--send CE command to get last ensemble (wait for response)
        ### adcpt--make sure ensemble goes through parser!!
        ### adcpt--ok to leave new values in cache?? Steve F. 
        ### says inefficient to call
        ###    _build_param_dict every time.
        self._do_cmd_no_resp(InstrumentCmds.SEND_LAST_DATA_ENSEMBLE)

        self._build_param_dict()

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)


    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.
        Pass it to extract_sample with the appropriate particle
        objects and REGEXes.
        """
        if(self._extract_sample(ADCPT_EnsembleDataParticle, ENSEMBLE_REGEX_MATCHER, chunk, timestamp)):
            log.debug("successful extract_sample for ENSEMBLE")
            return

        if(self._extract_sample(ADCPT_CalibrationDataParticle, CALIBRATION_DATA_REGEX_MATCHER, chunk, timestamp)):
            log.debug("successful extract_sample for CALIBRATION")
            return

        if(self._extract_sample(ADCPT_PS0DataParticle, PS0_REGEX_MATCHER, chunk, timestamp)):
            log.debug("successful extract_sample for PS0")
            return

        if(self._extract_sample(ADCPT_PS3DataParticle, PS3_REGEX_MATCHER, chunk, timestamp)):
            log.debug("successful extract_sample for PS3")
            return

        if(self._extract_sample(ADCPT_FDDataParticle, FD_REGEX_MATCHER, chunk, timestamp)):
            log.debug("successful extract_sample for FD")
            return

        if(self._extract_sample(ADCPT_PT200DataParticle, PT200_REGEX_MATCHER, chunk, timestamp)):
            log.debug("successful extract_sample for PT200")
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
    def _parse_display_system_configuration_response(self, *args, **kwargs):
        pass

    def _parse_display_transformation_matrix_response(self, *args, **kwargs):
        pass

    def _parse_display_fault_log_response(self, *args, **kwargs):
        pass

    def _parse_built_in_test_response(self, *args, **kwargs):
        pass

    def _parse_output_calibration_data_response(self, *args, **kwargs):
        pass

    def _parse_display_fatory_calibration_response(self, *args, **kwargs):
        pass

    ########################################################################
    # Unknown handlers.
    ########################################################################
    def _handler_unknown_break_success(self, *args, **kwargs):
        """
        Handles the event BREAK being successfully received by the adcpt
        """
        log.debug("FSM_TRACKER: in _handler_unknown_break_success")
        next_state = ProtocolState.COMMAND
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        return(next_state)

    def _handler_unknown_break_alarm(self, *args, **kwargs):
        """
        Handles the event BREAK-ALARM being received by the adcpt
        and responding with this because the internal battery is low.
        Typically don't want to deploy if this is the case.
        """
        log.debug("FSM_TRACKER: in _handler_unknown_break_alarm")
        next_state = None
        return(next_state)

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        log.debug("FSM_TRACKER: in _handler_unknown_enter")

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        log.debug("FSM_TRACKER: in _handler_unknown_exit")

        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result), (ProtocolState.COMMAND or
        State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not
        correspond to an expected state.
        """
        log.debug("FSM_TRACKER: in _handler_unknown_discover")

        timeout = kwargs.get('timeout', TIMEOUT)

        current_state = self._protocol_fsm.get_current_state()

        if current_state == ProtocolState.AUTOSAMPLE:
            result = ResourceAgentState.STREAMING

        elif current_state == ProtocolState.COMMAND:
            result = ResourceAgentState.IDLE

        elif current_state == ProtocolState.UNKNOWN:

            # Wakeup the device with timeout if passed.

            delay = 0.5

            prompt = self._wakeup(timeout=timeout, delay=delay)
            prompt = self._wakeup(timeout)
            result = ResourceAgentState.IDLE
        # Set the state to change.
        # Raise if the prompt returned does not match command or autosample.

        pd = self._param_dict.get_config()

        """
        if pd[Parameter.LOGGING] == True:
            next_state = ProtocolState.AUTOSAMPLE
            result = ResourceAgentState.STREAMING
        elif pd[Parameter.LOGGING] == False:
            next_state = ProtocolState.COMMAND
            result = ResourceAgentState.IDLE
        else:
            raise InstrumentStateException('Unknown state.')
        """
        next_state = ProtocolState.COMMAND
        return (next_state, result)

    ########################################################################
    # Command handlers.
    ########################################################################
    _command_set_cmds = [
                    InstrumentCmds.COMM_PARAMS_DEFAULT]

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not 
        recognized.
        """
        log.debug("FSM_TRACKER: in _handler_command_enter")

        instrument_setup_cmds = [
            InstrumentCmds.COMM_PARAMS_DEFAULT,
            InstrumentCmds.COLLECTION_MODE_DEFAULT,
            InstrumentCmds.SPEED_OF_SOUND_DEFAULT,
            InstrumentCmds.INSTRUMENT_ID_DEFAULT,
            InstrumentCmds.SALINITY_DEFAULT,
            InstrumentCmds.TIME_PER_BURST_DEFAULT,
            InstrumentCmds.ENSEMBLES_PER_BURST_DEFAULT,
            InstrumentCmds.TIME_PER_ENSEMBLE_DEFAULT,
            InstrumentCmds.TIME_OF_FIRST_PING_DEFAULT,
            InstrumentCmds.TIME_OF_FIRST_PING_Y2K_DEFAULT,
            InstrumentCmds.TIME_BETWEEN_PINGS_DEFAULT,
            InstrumentCmds.REAL_TIME_CLOCK_DEFAULT,
            InstrumentCmds.REAL_TIME_CLOCK_Y2K_DEFAULT,
            InstrumentCmds.BUFFERED_OUTPUT_PERIOD_DEFAULT,
            InstrumentCmds.NUMBER_OF_DEPTH_CELLS_DEFAULT,
            InstrumentCmds.PINGS_PER_ENSEMBLE_DEFAULT,
            InstrumentCmds.DEPTH_CELL_SIZE_DEFAULT,
            InstrumentCmds.TRANSMIT_LENGTH_DEFAULT,
            InstrumentCmds.PING_WEIGHT_DEFAULT,
            InstrumentCmds.AMBIGUITY_VELOCITY_DEFAULT]

        # make sure comm is set up properly.
        # send these commands first, because their default values could override
        # something you have set if you run these last.

        # Command device to update parameters and send a config change event.

        self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        for cmd in instrument_setup_cmds:
            result = self._do_cmd_no_resp(cmd)

        next_agent_state = None
        result = None
#        next_state = ProtocolState.COMMAND
        next_state = None
        return (next_state, (next_agent_state, result))

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """
        log.debug("FSM_TRACKER: in _handler_command_get")
        next_state = ProtocolState.COMMAND
        self._build_param_dict()  # make sure data is up-to-date
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


    ################################
    # SET
    ################################

    #REDONE#
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

    #REDONE#
    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
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

        self._update_params()

    #REDONE#
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
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return set_cmd

    #REDONE#
    def _parse_set_response(self, response, prompt):
        """
        Parse handler for set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """

        if prompt == Prompt.ERR:
            raise InstrumentProtocolException('Protocol._parse_set_response : Set command not recognized: %s' % response)

    #REDONE#
    def _handler_command_self_deploy(self, *args, **kwargs):
        """
        Handler for event where adcpt automatically reverts to AUTOSAMPLE from
        COMMAND state after several minutes of inactivity
        """
        log.debug("FSM_TRACKER: in _handler_autosample_self_deploy")
        next_state = ProtocolState.AUTOSAMPLE
        return(next_state)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Go into AUTOSAMPLE state when sent command to start.
        'CS' is the adcpt command to start sampling.
        """
        log.debug("FSM_TRACKER: in _handler_command_start_autosample")
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        result = None
        return (next_state, (next_agent_state, result)) 

    def _handler_command_quit_session(self, *args, **kwargs):
        """
        Power-down the instrument when sent a QUIT_SESSION command.
        'CZ' is the adcpt command to power down.
        """
        next_state = None

        result = self._do_cmd_no_resp(InstrumentCmds.POWER_DOWN, *args, **kwargs)
        return (next_state, result)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Handles exiting the command state
        (only possible by sending a BREAK command to the instrument)
        """
        global command_set_cmds
        # send the commands that accumulated during 'execute'
        log.debug("FSM_TRACKER: in _handler_command_exit")

        final_before_deploy_cmds = [
            InstrumentCmds.SAVE_SETUP_TO_RAM,
            InstrumentCmds.START_DEPLOYMENT]

        self._command_set_cmds.extend(final_before_deploy_cmds)
        for cmd in self._command_set_cmds:
            self._do_cmd_no_resp(cmd)

        #send cmds sent other than minimum required
        #send remaining min req'd cmds

        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = None
        result = None
        return (next_state, (next_agent_state, result))

    def _handler_command_powering_down(self, *args, **kwargs):
        """
        Executed when no commands have been received in several minutes
        after entering COMMAND state.
        """
        log.debug("^^^^ FSM_TRACKER: in _handler_command_powering_down")
        next_state = ProtocolState.UNKNOWN
        return(next_state)

    ########################################################################
    # Autosample handlers.
    ########################################################################
    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Called when exiting autosample state.
        """
        log.debug("^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_autosample_exit")

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Called on entry to autosample state.
        """
        log.debug("^^^^^^^^^^^^^ FSM_TRACKER: in _handler_autosample_enter")
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_break_success(self, *args, **kwargs):
        """
        Break was received while autosampling; return to COMMAND state.
        """
        log.debug("^^^^^^^ FSM_TRACKER: in _handler_autosample_break_success")
        next_state = ProtocolState.COMMAND
        return(next_state)

    def _handler_autosample_break_alarm(self, *args, **kwargs):
        """
        Handles receiving a ? command while autosampling.
        """
        log.debug("^^^^^^^ FSM_TRACKER: in _handler_autosample_break_alarm")

    def _handler_autosample_get(self, *args, **kwargs):
        """
        Gets the value of a parameter
        """
        log.debug("^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_autosample_get")

        self._build_param_dict()  # make sure data is up-to-date
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

    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_command_start_direct(self, *args, **kwargs):
        """
        Start direct access
        """

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

    def _handler_direct_access_execute_direct(self, data):
        """
        Execute direct access.
        @data The command to be added to list for 'echo' filtering
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

        result = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        pass

    ########################################################################
    # Static helpers to format set commands.
    ########################################################################

    @staticmethod
    def _string_to_string(v):
        return v

    @staticmethod
    def _bool_to_int(v):
        """
        Write a bool value to string as an int.
        @param v A bool val.
        @retval a int string.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v, int):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            if v:
                return 1
            else:
                return 0

    @staticmethod
    def _reverse_bool_to_int(v):
        """
        Write a inverse-bool value to string as an int.
        @param v A bool val.
        @retval a int string.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v, int):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            if v:
                return 0
            else:
                return 1

    @staticmethod
    def _float_to_string(v):
        """
        Write a float value to string.
        @param v a float val.
        @retval a float string formatted.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v, float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            return str(v)  # return a simple float

    @staticmethod
    def _time_to_string(v):
        """
        Write a time value to string.
        @param v a time val.
        @retval a time string formatted.
        @throws InstrumentParameterException if value is not a time.
        """

        if not isinstance(v, time):
            raise InstrumentParameterException('Value %s is not a time.' % v)
        else:
            return time.strftime("%H:%M:%S", v)

    @staticmethod
    def _datetime_with_milis_to_time_string_with_milis(v):
        """
        Write a datetime value to string.
        @param v a datetime val.
        @retval a time w/milis string formatted.
        @throws InstrumentParameterException if value is not a datetime.
        """

        if not isinstance(v, datetime):
            raise InstrumentParameterException('Value %s is not a datetime.' % v)
        else:
            return datetime.strftime(v, '%H:%M:%S.%f')

    @staticmethod
    def _datetime_YYYY_to_string(v):
        """
        Write a time value to string.
        @param v a time val.
        @retval a time with date string formatted.
        @throws InstrumentParameterException if value is not a datetime.
        """

        if not isinstance(v, time):
            raise InstrumentParameterException('Value %s is not a datetime.' % v)
        else:
            return time.strftime("%Y/%m/%d,%H:%M:%S", v)

    @staticmethod
    def _datetime_YY_to_string(v):
        """
        Write a time value to string.
        @param v a time val.
        @retval a time with date string formatted.
        @throws InstrumentParameterException if value is not a datetime.
        """

        if not isinstance(v, time):
            raise InstrumentParameterException('Value %s is not a datetime.' % v)
        else:
            return time.strftime("%y/%m/%d,%H:%M:%S", v)