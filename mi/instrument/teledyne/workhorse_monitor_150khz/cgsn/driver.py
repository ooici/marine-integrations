"""
@package mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver
@file marine-integrations/mi/instrument/teledyne/workhorse_monitor_150khz/cgsn/driver.py
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

from distutils.log import warn as printf
from json import dumps
from pprint import pprint


# newline.
NEWLINE = '\n'

# default timeout.
TIMEOUT = 10

BYTE_SIZE = 2                   #number of chars per byte
WORD_SIZE = 4                   #number of chars per 2-byte word

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




ENSEMBLE_HEADER_ID = '7F7F'
FIXED_LEADER_ID = '0000'
VAR_LEADER_ID = '8000'
VELOCITY_ID = '0001'
CORR_MAG_ID = '0002'
ECHO_INTENSITY_ID = '0003'
PERCENT_GOOD_ID = '0004'
STATUS_ID = '0005'
BOTTOM_TRACK_ID = '0006'
ENSEMBLE_LENGTH_LOC = 4         #index in header where number of bytes in ensemble is located

## globals
NumCells = 0              #value from fixed leader datq; used to determine size of velocity and other data records.
num_data_types = 0        #value from header data; used to determine size of header record and total number of data records.
num_bytes_in_ensemble = 0 #value from header data; used to determine size of ensemble and calculate checksum.

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    ENSEMBLE_PARSED = 'ensemble_parsed'
    CALIBRATION_PARSED = 'calibration_parsed'
    PS0_PARSED = 'ps0_parsed'
    PS3_PARSED = 'ps3_parsed'
    FD_PARSED = 'fd_parsed'
    PT200_PARSED = 'pt200_parsed'

class InstrumentCmds(BaseEnum):
    """
    Device specific commands
    Represents the commands the driver implements and the string that must be sent to the instrument to
    execute the command.
    """
    BREAK = 'break 500'

    ### -- startup cmds
    RETRIEVE_FACTORY_SETUP = 'CR1'
    COMM_PARAMS_DEFAULT = 'CB411'  #9600 baud, no parity, 1 stop bit
    COLLECTION_MODE_DEFAULT = 'CF11211'   #data comes out as ascii-hex
    SPEED_OF_SOUND_DEFAULT = 'EC1500'
    INSTRUMENT_ID_DEFAULT = 'CI000'
    SALINITY_DEFAULT = 'ES35'  #would be overwritten if there were a salinity sensor, but default is NO SALINITY SENSOR
    TIME_PER_BURST_DEFAULT = 'TB00:00:00:00'
    ENSEMBLES_PER_BURST_DEFAULT =  'TC0'
    TIME_PER_ENSEMBLE_DEFAULT =  'TE01:00:00:00'
    TIME_OF_FIRST_PING_DEFAULT = 'TF00/00/00,00:00:00'  #yy/mm/dd, hh:mm:ss
    TIME_OF_FIRST_PING_Y2K_DEFAULT = 'TG0000/00/00,00:00:00'  #ccyy/mm/dd, hh:mm:ss
    TIME_BETWEEN_PINGS_DEFAULT =  'TP01:20:00'
    REAL_TIME_CLOCK_DEFAULT = 'TS00/00/00,00:00:00'  #yy/mm/dd, hh:mm:ss
    REAL_TIME_CLOCK_Y2K_DEFAULT = 'TT0000/00/00,00:00:00'  #ccyy/mm/dd, hh:mm:ss
    BUFFERED_OUTPUT_PERIOD_DEFAULT = 'TX00:00:00'
    NUMBER_OF_DEPTH_CELLS_DEFAULT =  'WN30'
    PINGS_PER_ENSEMBLE_DEFAULT =  'WP45'
    DEPTH_CELL_SIZE_DEFAULT =  'WS800'
    TRANSMIT_LENGTH_DEFAULT = 'WT0'
    PING_WEIGHT_DEFAULT = 'WU0'
    AMBIGUITY_VELOCITY_DEFAULT = 'WV175'

    TIME_PER_BURST = 'TIME_PER_BURST'
    ENSEMBLES_PER_BURST = 'ENSEMBLES_PER_BURST'
    TIME_PER_ENSEMBLE = 'TIME_PER_ENSEMBLE'
    TIME_OF_FIRST_PING = 'TIME_OF_FIRST_PING'
    TIME_OF_FIRST_PING_Y2K = 'TIME_OF_FIRST_PING_Y2K'
    TIME_BETWEEN_PINGS = 'TIME_BETWEEN_PINGS'
    REAL_TIME_CLOCK = 'REAL_TIME_CLOCK'
    REAL_TIME_CLOCK_Y2K = 'REAL_TIME_CLOCK_Y2K'
    BUFFERED_OUTPUT_PERIOD = 'BUFFERED_OUTPUT_PERIOD'
    FALSE_TARGET_THRESHOLD_MAXIMUM = 'FALSE_TARGET_THRESHOLD_MAXIMUM'
    LOW_CORRELATION_THRESHOLD = 'LOW_CORRELATION_THRESHOLD'  #same as LOW_CORR_THRESH in particle; WC cmd.
    ERROR_VELOCITY_THRESHOLD = 'ERROR_VELOCITY_THRESHOLD'  #same as ERR_VEL_MAX in particle; initially set by WE.
    CLIP_DATA_PAST_BOTTOM = 'CLIP_DATA_PAST_BOTTOM'
    RECEIVER_GAIN_SELECT = 'RECEIVER_GAIN_SELECT'
    WATER_REFERENCE_LAYER = 'WATER_REFERENCE_LAYER'  #tuple, same as particle (WL cmd)
    NUMBER_OF_DEPTH_CELLS = 'NUMBER_OF_DEPTH_CELLS' #same as NUM_CELLS in particle
    PINGS_PER_ENSEMBLE = 'PINGS_PER_ENSEMBLE'  #same as in particle
    DEPTH_CELL_SIZE = 'DEPTH_CELL_SIZE'  #same as DEPTH_CELL_LEN in particle
    TRANSMIT_LENGTH = 'TRANSMIT_LENGTH'  #different than XMIT_PULSE_LEN(WT) in particle.
    PING_WEIGHT = 'PING_WEIGHT'
    AMBIGUITY_VELOCITY = 'AMBIGUITY_VELOCITY'

    ### -- set commands
    SET_TRANSMIT_POWER = 'CQ'
    SET_SPEED_OF_SOUND = 'EC'
    SET_SALINITY = 'ES'
    SET_TIME_PER_BURST = 'TB'
    SET_ENSEMBLES_PER_BURST = 'TC'
    SET_TIME_PER_ENSEMBLE = 'TE'
    SET_TIME_OF_FIRST_PING = 'TF'
    SET_TIME_OF_FIRST_PING_Y2K = 'TG'
    SET_TIME_BETWEEN_PINGS = 'TP'
    SET_REAL_TIME_CLOCK = 'TS'
    SET_REAL_TIME_CLOCK_Y2K = 'TT'
    SET_BUFFERED_OUTPUT_PERIOD = 'TX'
    SET_FALSE_TARGET_THRESHOLD_MAXIMUM = 'WA'
    SET_LOW_CORRELATION_THRESHOLD = 'WC'
    SET_ERROR_VELOCITY_THRESHOLD = 'WE'
    SET_CLIP_DATA_PAST_BOTTOM= 'WI'
    SET_RECEIVER_GAIN_SELECT = 'WJ'
    SET_WATER_REFERENCE_LAYER = 'WL'
    SET_NUMBER_OF_DEPTH_CELLS = 'WN'
    SET_PINGS_PER_ENSEMBLE = 'WP'
    SET_DEPTH_CELL_SIZE = 'WS'
    SET_TRANSMIT_LENGTH = 'WT'
    SET_PING_WEIGHT = 'WU'
    SET_AMBIGUITY_VELOCITY = 'WV'
    SET_MODE_1_BANDWIDTH_CONTROL = 'WB'
    SET_BLANK_AFTER_TRANSMIT = 'WF'
    SET_DATA_OUT = 'WD'
    SET_INSTRUMENT_ID = 'CI'
    SET_WATER_PROFILING_MODE = 'WM'

    ### -- action commands
    POWER_DOWN = 'CZ'
    START_DEPLOYMENT = 'CS'
    SAVE_SETUP_TO_RAM = 'CK'
    SEND_LAST_DATA_ENSEMBLE = 'CE'
    CLEAR_ERROR_STATUS_WORD = 'CY0'
    DISPLAY_ERROR_STATUS_WORD = 'CY1'
    CLEAR_FAULT_LOG = 'FC'
    DISPLAY_FACTORY_CALIBRATION = 'AD'
    DISPLAY_SYSTEM_CONFIGURATION = 'PS0'
    DISPLAY_TRANSFORMATION_MATRIX = 'PS3'
    DISPLAY_FAULT_LOG = 'FD'
    BUILT_IN_TEST = 'PT200'
    OUTPUT_CALIBRATION_DATA = 'AC'
    POLLED_MODE_OFF = 'CP0'

    
class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS



class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    BREAK_ALARM = 'BREAK_ALARM'
    BREAK_SUCCESS = 'BREAK_SUCCESS'
    START_AUTOSAMPLE = 'START_AUTOSAMPLE'
    SELF_DEPLOY = 'SELF_DEPLOY'
    POWERING_DOWN = 'POWERING_DOWN'
    #
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    DISCOVER = DriverEvent.DISCOVER
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    QUIT_SESSION = 'PROTOCOL_EVENT_QUIT_SESSION'

    
class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    QUIT_SESSION = ProtocolEvent.QUIT_SESSION
    
class Parameter(DriverParameter):
    """
    Device parameters
    """
    ### --settable parameters
    TRANSMIT_POWER = 'TRANSMIT_POWER'  #same as SystemPower in particle
    SPEED_OF_SOUND = 'SPEED_OF_SOUND'  #same as in particle
    SALINITY = 'SALINITY'  #same as in particle
    TIME_PER_BURST = 'TIME_PER_BURST'
    ENSEMBLES_PER_BURST = 'ENSEMBLES_PER_BURST'
    TIME_PER_ENSEMBLE = 'TIME_PER_ENSEMBLE'
    TIME_OF_FIRST_PING = 'TIME_OF_FIRST_PING'
    TIME_OF_FIRST_PING_Y2K = 'TIME_OF_FIRST_PING_Y2K'
    TIME_BETWEEN_PINGS = 'TIME_BETWEEN_PINGS'
    REAL_TIME_CLOCK = 'REAL_TIME_CLOCK'
    REAL_TIME_CLOCK_Y2K = 'REAL_TIME_CLOCK_Y2K'
    BUFFERED_OUTPUT_PERIOD = 'BUFFERED_OUTPUT_PERIOD'
    FALSE_TARGET_THRESHOLD_MAXIMUM = 'FALSE_TARGET_THRESHOLD_MAXIMUM'
    LOW_CORRELATION_THRESHOLD = 'LOW_CORRELATION_THRESHOLD'  #same as LOW_CORR_THRESH in particle; WC cmd.
    ERROR_VELOCITY_THRESHOLD = 'ERROR_VELOCITY_THRESHOLD'  #same as ERR_VEL_MAX in particle; initially set by WE.
    CLIP_DATA_PAST_BOTTOM = 'CLIP_DATA_PAST_BOTTOM'
    RECEIVER_GAIN_SELECT = 'RECEIVER_GAIN_SELECT'
    WATER_REFERENCE_LAYER = 'WATER_REFERENCE_LAYER'  #tuple, same as particle (WL cmd)
    NUMBER_OF_DEPTH_CELLS = 'NUMBER_OF_DEPTH_CELLS' #same as NUM_CELLS in particle
    PINGS_PER_ENSEMBLE = 'PINGS_PER_ENSEMBLE'  #same as in particle
    DEPTH_CELL_SIZE = 'DEPTH_CELL_SIZE'  #same as DEPTH_CELL_LEN in particle
    TRANSMIT_LENGTH = 'TRANSMIT_LENGTH'  #different than XMIT_PULSE_LEN(WT) in particle.
    PING_WEIGHT = 'PING_WEIGHT'
    AMBIGUITY_VELOCITY = 'AMBIGUITY_VELOCITY'
    MODE_1_BANDWIDTH_CONTROL = 'MODE_1_BANDWIDTH_CONTROL'
    BLANK_AFTER_TRANSMIT = 'BLANK_AFTER_TRANSMIT'
    DATA_OUT = 'DATA_OUT'
    INSTRUMENT_ID = 'INSTRUMENT_ID'
    WATER_PROFILING_MODE = 'WATER_PROFILING_MODE'
    
    
class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """
    COMMAND = '>'
    AUTOSAMPLE = ''


####################################################
#  The adcpt_cache_dict is used to store data parsed
#  in the ADCPT_EnsembleDataParticleKey class; this data
#  is then used by the Protocol class as a source of
#  parameter data which can't be obtained by querying
#  the instrument with GET commands.
#  The initial data in the cache has been set to default
#  values for the parameters, in case they are used
#  before being modified by user.
#####################################################
adcpt_cache_dict = {
    'TRANSMIT_POWER' : 255, 
    'SPEED_OF_SOUND'  : 1500,
    'SALINITY' :  35,
    'TIME_PER_BURST' : '00:00:00:00' ,
    'ENSEMBLES_PER_BURST' :  0,
    'TIME_PER_ENSEMBLE' :  '01:00:00:00',
    'TIME_OF_FIRST_PING' : '00/00/00, 00:00:00',
    'TIME_OF_FIRST_PING_Y2K' : '0000/00/00, 00:00:00',
    'TIME_BETWEEN_PINGS' :  '01:20:00',
    'REAL_TIME_CLOCK' : '00/00/00, 00:00:00',
    'REAL_TIME_CLOCK_Y2K' : '0000/00/00, 00:00:00',
    'BUFFERED_OUTPUT_PERIOD' : '00:00:00' ,
    'FALSE_TARGET_THRESHOLD_MAXIMUM' :  50,
    'LOW_CORRELATION_THRESHOLD' : 64,
    'ERROR_VELOCITY_THRESHOLD' :  2000,
    'CLIP_DATA_PAST_BOTTOM' :  0,
    'RECEIVER_GAIN_SELECT' :  1,
    'WATER_REFERENCE_LAYER' : [1,5],
    'NUMBER_OF_DEPTH_CELLS' :  30,
    'PINGS_PER_ENSEMBLE' :  45,
    'DEPTH_CELL_SIZE' :  800,
    'TRANSMIT_LENGTH' : 0 ,
    'PING_WEIGHT' :  0,
    'AMBIGUITY_VELOCITY': 175,
    'MODE_1_BANDWIDTH_CONTROL' : 1,
    'BLANK_AFTER_TRANSMIT' : 352,
    'DATA_OUT' : 111100000,
    'INSTRUMENT_ID' : 0,
    'WATER_PROFILING_MODE' : 1 }

###############################################################################
# Data Particles
###############################################################################
class ADCPT_PS0DataParticleKey(BaseEnum):
    PS0_DATA = "ps0_data"
    
class ADCPT_PS0DataParticle(DataParticle):
    _data_particle_type = DataParticleType.PS0_PARSED

    def _build_parsed_values(self):
        result = []
        data_stream = self.raw_data
        m = re.search(ps0_regex,data_stream)
        if m is not None:
            value = m.group()[:-1]
        else:
            value = None
        result = [{DataParticleKey.VALUE_ID: ADCPT_PS0DataParticleKey.PS0_DATA,
                   DataParticleKey.VALUE: value}]

class ADCPT_PS3DataParticleKey(BaseEnum):
    PS3_DATA = "ps3_data"
    
class ADCPT_PS3DataParticle(DataParticle):
    _data_particle_type = DataParticleType.PS3_PARSED

    def _build_parsed_values(self):
        result = []
        data_stream = self.raw_data
        m = re.search(ps3_regex,data_stream)
        if m is not None:
            value = m.group()[:-1]
        else:
            value = None
        result = [{DataParticleKey.VALUE_ID: ADCPT_PS3DataParticleKey.PS3_DATA,
                   DataParticleKey.VALUE: value}]

class ADCPT_FDDataParticleKey(BaseEnum):
    FD_DATA = "fd_data"
    
class ADCPT_FDDataParticle(DataParticle):
    _data_particle_type = DataParticleType.FD_PARSED

    def _build_parsed_values(self):
        result = []
        data_stream = self.raw_data
        m = re.search(fd_regex,data_stream)
        if m is not None:
            value = m.group()[:-1]
        else:
            value = None
        result = [{DataParticleKey.VALUE_ID: ADCPT_FDDataParticleKey.FD_DATA,
                   DataParticleKey.VALUE: value}]

class ADCPT_PT200DataParticleKey(BaseEnum):
    PT200_DATA = "pt200_data"
    
class ADCPT_PT200DataParticle(DataParticle):
    _data_particle_type = DataParticleType.PT200_PARSED

    def _build_parsed_values(self):
        result = []
        data_stream = self.raw_data
        m = re.search(pt200_regex,data_stream)
        if m is not None:
            value = m.group()[:-1]
        else:
            value = None
        result = [{DataParticleKey.VALUE_ID: ADCPT_PT200DataParticleKey.FD_DATA,
                   DataParticleKey.VALUE: value}]

class ADCPT_CalibrationDataParticleKey(BaseEnum):
    CALIBRATION_DATA = "calibration_data"
    
class ADCPT_CalibrationDataParticle(DataParticle):
    _data_particle_type = DataParticleType.ENSEMBLE_PARSED

    def _build_parsed_values(self):
        result = []
        data_stream = self.raw_data
        m = re.search(calibration_regex,data_stream)
        if m is not None:
            value = m.group()[:-1]
        else:
            value = None
        result = [{DataParticleKey.VALUE_ID: ADCPT_CalibrationDataParticleKey.CALIBRATION_DATA,
                   DataParticleKey.VALUE: value}]

class ADCPT_EnsembleDataParticleKey(BaseEnum):
    NUM_BYTES_IN_ENSEMBLE = "Ensemble bytes"
    NUM_DATA_TYPES = "NumTypes"
#-------fixed leader data format------------
    CPU_FW_VER = "CPU_fw_ver"
    CPU_FW_REV = "CPU_fw_rev"
    SYS_CONFIG = "SysConfig"
    LAG_LEN = "LagLength"
    NUM_BEAMS = "NumBeams"
    NUM_CELLS = "NumCells"  #same as NUMBER_OF_CELLS in parameters
    PINGS_PER_ENSEMBLE = "Pings_per_ensemble"  #same as in parameters
    DEPTH_CELL_LEN = "Depth_cell_length"  #same as DEPTH_CELL_SIZE in parameters
    BLANK_AFTER_TX = "Blank_after_transmit"
    PROFILING_MODE = "Profiling_Mode"
    LOW_CORR_THRESH = "Low_correlation_threshold"  #same as LOW_CORRELATION_THRESHOLD in parameters
    NUM_CODE_REPS = "Number_of_code_repetitions"
    PERCENT_GD_MIN = "Percent_of_GD_minimum"
    ERR_VEL_MAX = "Error_velocity_maximum"  #same as ERROR_VELOCITY_THRESHOLD in parameters
    TIME_BETWEEN_PINGS = "Time_between_pings"
    COORD_XFRM = "Coordinate_transform"
    HEAD_ALIGN = "Heading_alignment"
    HEAD_BIAS  = "Heading_bias"
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
    XMIT_PULSE_LEN = "Xmit_Pulse_Length"  #different than TRANSMIT_LENGTH in params
    WP_REF_LAYER_AVG = "WP_ref_layer_avg"  #tuple, same as parameters.
    FALSE_TARGET_THRESH = "False_Target_Threshold"
    XMIT_LAG_DIST = "Transmit_Lag_Distance"
    CPU_SN = "CPU_board_serial_number"
    SYS_BW = "System_Bandwidth"  #same as MODE_1_BANDWIDTH_CONTROL in parameters
    SYS_PWR = "System_Power"  #same as TransmitPower in parameters
    INST_SN = "Instrument_Serial_Number"
    BEAM_ANGLE = "Beam_Angle"
#-------var leader data format------------
    ENSEMBLE_NUMBER = "Ensemble_Number"
    RTC_DATE_TIME = "RTC_date_time"
    TIMESTAMP = "timestamp"
    ENSEMBLE_NUM_MSB = "Ensemble_number_msb"
    BIT_RESULT = "Built_in_Test_Results"
    SPEED_OF_SOUND = "Speed_of_sound"  #same as in parameters
    DEPTH_OF_XDUCER = "Depth_of_transducer"
    HEADING = "Heading"
    PITCH = "Pitch"
    ROLL = "Roll"
    SALINITY = "Salinity"  #same as in parameters
    TEMPERATURE = "Temperature"
    MIN_PRE_PING_WAIT_TIME = "Min_pre_ping_wait_time"
    HDG_DEV = "Heading_deviation"
    PITCH_DEV = "Pitch_deviation"
    ROLL_DEV = "Roll_deviation"
    XMIT_CURRENT = "Xmit_current"
    XMIT_VOLTAGE = "Xmit_voltage"
    AMBIENT_TEMP  = "Ambient_temp"
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

    def get_byte_value(self,str,index):
        """
        Returns value of a byte (2 characters) in an ascii-hex string into a decimal integer
        """
        return int(str[index:index+BYTE_SIZE],16)
     
    def get_word_value(self,str,index):
        """
        Returns value of a 2-byte word (4 characters) in an ascii-hex string into a decimal integer
        """
        upper_byte_loc = index+BYTE_SIZE
        lower_byte_loc = index
        return int(str[upper_byte_loc:upper_byte_loc + BYTE_SIZE]+
                   str[lower_byte_loc:lower_byte_loc + BYTE_SIZE],16)
    
    def get_double_word_value(self,str,index):
        """
        Returns value of a 4-byte word (8 characters) in an ascii-hex string into a decimal integer
        """
        upper_byte_loc = index+3*BYTE_SIZE
        upper_middle_byte_loc = index+2*BYTE_SIZE
        lower_middle_byte_loc = index+BYTE_SIZE
        lower_byte_loc = index
        return int(str[upper_byte_loc:upper_byte_loc + BYTE_SIZE] +\
                   str[upper_middle_byte_loc:upper_middle_byte_loc + BYTE_SIZE] +
                   str[lower_middle_byte_loc:lower_middle_byte_loc + BYTE_SIZE] +
                   str[lower_byte_loc:lower_byte_loc + BYTE_SIZE], 16)
    
    def get_signed_word_value(self,str,index):
        """
        Returns value of a 2-byte word (4 characters) in an ascii-hex string into a decimal integer,
        but if msbit of word is '1', it is assumed to be a negative number, so two's complement it.
        """
        upper_byte_loc = index+BYTE_SIZE
        lower_byte_loc = index
        temp = int(str[upper_byte_loc:upper_byte_loc + BYTE_SIZE]+
                   str[lower_byte_loc:lower_byte_loc + BYTE_SIZE],16)
        if temp > 0x7fff:
            temp ^= 0xffff
            temp *= -1
            temp -= 1
        return temp
           
    def get_two_byte_string(self,str,index):
        """
        Returns string of the two 2-char bytes at index (transpose the bytes, but leave as string value
        """
        upper_byte_loc = index+BYTE_SIZE
        lower_byte_loc = index
        return (str[upper_byte_loc:upper_byte_loc + BYTE_SIZE] +
                str[lower_byte_loc:lower_byte_loc + BYTE_SIZE])
    
    def calc_checksum(self,str, num_bytes):
        sum = 0
        for i in range(0,num_bytes*2,2):
            sum += self.get_byte_value(str,i)
        return hex(sum)[-4:]
        
    # These parse_xxxx_record functions are called when one of the data types in an ensemble has been identified.
    # They return a list of dictionaries corresponding to the data in each unique data type in input 'str'.
    # 'start_index' is the index of the first location in the record, since the documentation refers to data locations
    # relative to start of record.
    # !! the relative positions of data in the records are hard-coded 'magic' number; they appear as hard-coded
    #   values because:
    #   1) dreaming up defines for each would be confusing (very easy to understand the intent of the code as written),
    #   2) the data formats are clearly documented by the manufacturer (see IOS),
    #   3) the data formats are very unlikely to change (too much manufacturer and users code would break)
    
    def parse_fixed_leader_record(self,str,start_index):
        global NumCells
        retlist = []
        CPU_fw_ver = self.get_byte_value(str,start_index + 4)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CPU_FW_VER,
                       DataParticleKey.VALUE: CPU_fw_ver})
        CPU_fw_rev = self.get_byte_value(str,start_index + 6)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CPU_FW_REV,
                       DataParticleKey.VALUE: CPU_fw_rev})
        SysConfig = self.get_word_value(str,start_index + 8)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SYS_CONFIG,
                       DataParticleKey.VALUE: SysConfig})
        LagLength = self.get_byte_value(str,start_index + 14)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.LAG_LEN,
                       DataParticleKey.VALUE: LagLength})
        NumBeams = self.get_byte_value(str,start_index + 16)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.NUM_BEAMS,
                       DataParticleKey.VALUE: NumBeams})
        NumCells = self.get_byte_value(str,start_index + 18)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.NUM_CELLS,
                       DataParticleKey.VALUE: NumCells})
        adcpt_cache_dict[Parameter.NUMBER_OF_DEPTH_CELLS] = NumCells
        PingsPerEnsemble = self.get_word_value(str,start_index + 20)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PINGS_PER_ENSEMBLE,
                       DataParticleKey.VALUE: PingsPerEnsemble})
        adcpt_cache_dict[Parameter.PINGS_PER_ENSEMBLE] = PingsPerEnsemble
        DepthCellLength = self.get_word_value(str,start_index + 24)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.DEPTH_CELL_LEN,
                       DataParticleKey.VALUE: DepthCellLength})
        adcpt_cache_dict[Parameter.DEPTH_CELL_SIZE] = DepthCellLength
        Blank_after_transmit = self.get_word_value(str,start_index + 28)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.BLANK_AFTER_TX,
                       DataParticleKey.VALUE: Blank_after_transmit})
        Profiling_Mode = self.get_byte_value(str,start_index + 32)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PROFILING_MODE,
                       DataParticleKey.VALUE: Profiling_Mode})
        Low_correlation_threshold = self.get_byte_value(str,start_index + 34)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.LOW_CORR_THRESH,
                       DataParticleKey.VALUE: Low_correlation_threshold})
        adcpt_cache_dict[Parameter.LOW_CORRELATION_THRESHOLD] = Low_correlation_threshold
        code_repetitions = self.get_byte_value(str,start_index + 36)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.NUM_CODE_REPS,
                       DataParticleKey.VALUE: code_repetitions})
        Percent_of_GD_minimum = self.get_byte_value(str,start_index + 38)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PERCENT_GD_MIN,
                       DataParticleKey.VALUE: Percent_of_GD_minimum})
        Error_velocity_maximum = self.get_word_value(str,start_index + 40)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ERR_VEL_MAX,
                       DataParticleKey.VALUE: Error_velocity_maximum})
        adcpt_cache_dict[Parameter.ERROR_VELOCITY_THRESHOLD] = Error_velocity_maximum
        Time_between_pings = [self.get_byte_value(str,start_index + 44),
                              self.get_byte_value(str,start_index + 46),
                              self.get_byte_value(str,start_index + 48)]
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.TIME_BETWEEN_PINGS,
                       DataParticleKey.VALUE: Time_between_pings})
        adcpt_cache_dict[Parameter.TIME_BETWEEN_PINGS] = Time_between_pings
        Coordinate_transform = self.get_byte_value(str,start_index + 50)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.COORD_XFRM,
                       DataParticleKey.VALUE: Coordinate_transform})
        Heading_alignment = self.get_word_value(str,start_index + 52)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.HEAD_ALIGN,
                       DataParticleKey.VALUE: Heading_alignment})
        Heading_bias = self.get_word_value(str,start_index + 56)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.HEAD_BIAS,
                       DataParticleKey.VALUE: Heading_bias})
        Sensor_source = self.get_byte_value(str,start_index + 60)
        working_list = []
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

        Sensor_availability = self.get_byte_value(str,start_index + 62)
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

        Distance_to_bin_1 = self.get_word_value(str,start_index + 64)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.BIN1_DIST,
                       DataParticleKey.VALUE: Distance_to_bin_1})
        Xmit_Pulse_Length = self.get_word_value(str,start_index + 68)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.XMIT_PULSE_LEN,
                       DataParticleKey.VALUE: Xmit_Pulse_Length})
        WP_ref_layer_avg = self.get_word_value(str,start_index + 72)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.WP_REF_LAYER_AVG,
                       DataParticleKey.VALUE: WP_ref_layer_avg})
        False_Target_Threshold = self.get_word_value(str,start_index + 76)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.FALSE_TARGET_THRESH,
                       DataParticleKey.VALUE: False_Target_Threshold})
        Transmit_Lag_Distance = self.get_word_value(str,start_index + 80)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.XMIT_LAG_DIST,
                       DataParticleKey.VALUE: Transmit_Lag_Distance})
        ### CPU serial number merely reported as raw string; not clear from documentation how to decode it.
        CPU_board_serial_number = str[start_index + 84:start_index+100]
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CPU_SN,
                       DataParticleKey.VALUE: CPU_board_serial_number})
        System_Bandwidth = self.get_word_value(str,start_index + 100)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SYS_BW,
                       DataParticleKey.VALUE: System_Bandwidth})
        System_Power = self.get_byte_value(str,start_index + 104)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SYS_PWR,
                       DataParticleKey.VALUE: System_Power})
        adcpt_cache_dict[Parameter.TRANSMIT_POWER] = System_Power
        ###### Instrument serial number merely reported as raw string; not clear from documentation how to decode it.
        Instrument_Serial_Number = str[start_index + 108:start_index + 116]
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.INST_SN,
                       DataParticleKey.VALUE: Instrument_Serial_Number})
        Beam_Angle = self.get_byte_value(str,start_index + 116)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.BEAM_ANGLE,
                       DataParticleKey.VALUE: Beam_Angle})
        return retlist
    
    def parse_var_leader_record(self,str,start_index):
        retlist = []
        Ensemble_Number = self.get_word_value(str,start_index + 4)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ENSEMBLE_NUMBER,
                       DataParticleKey.VALUE: Ensemble_Number})
        RTC_date_time = [self.get_byte_value(str,start_index + 8),self.get_byte_value(str,start_index + 10),
                         self.get_byte_value(str,start_index + 12),self.get_byte_value(str,start_index + 14),
                         self.get_byte_value(str,start_index + 16),self.get_byte_value(str,start_index + 18),
                         self.get_byte_value(str,start_index + 20)]
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.RTC_DATE_TIME,
                       DataParticleKey.VALUE: RTC_date_time})
        #Create a timestamp in ntp format
        struct_time = RTC_date_time[:6]
        hundredths = float(RTC_date_time[6])/100
        struct_time.extend([0,0,-1])
        timestamp = ntplib.system_to_ntp_time(time.mktime(struct_time)) + hundredths
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.TIMESTAMP,
                       DataParticleKey.VALUE: timestamp})
        Ensemble_number_msb = self.get_byte_value(str,start_index + 22)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ENSEMBLE_NUM_MSB,
                       DataParticleKey.VALUE: Ensemble_number_msb})
        Built_in_Test_Results = self.get_word_value(str,start_index + 24)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.BIT_RESULT,
                       DataParticleKey.VALUE: Built_in_Test_Results})
        Speed_of_sound = self.get_word_value(str,start_index + 28)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SPEED_OF_SOUND,
                       DataParticleKey.VALUE: Speed_of_sound})
        adcpt_cache_dict[Parameter.SPEED_OF_SOUND] = Speed_of_sound
        Depth_of_transducer = self.get_word_value(str,start_index + 32)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.DEPTH_OF_XDUCER,
                       DataParticleKey.VALUE: Depth_of_transducer})
        Heading = self.get_byte_value(str,start_index + 36)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.HEADING,
                       DataParticleKey.VALUE: Heading})
        Pitch = self.get_word_value(str,start_index + 40)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PITCH,
                       DataParticleKey.VALUE: Pitch})
        Roll = self.get_word_value(str,start_index + 44)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ROLL,
                       DataParticleKey.VALUE: Roll})
        Salinity = self.get_word_value(str,start_index + 48)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.SALINITY,
                       DataParticleKey.VALUE: Salinity})
        adcpt_cache_dict[Parameter.SALINITY] = Salinity
        Temperature = self.get_word_value(str,start_index + 52)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.TEMPERATURE,
                       DataParticleKey.VALUE: Temperature})
        Min_pre_ping_wait_time = [self.get_byte_value(str,start_index + 56),
                                  self.get_byte_value(str,start_index + 58),
                                  self.get_byte_value(str,start_index + 60)]
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.MIN_PRE_PING_WAIT_TIME,
                       DataParticleKey.VALUE: Min_pre_ping_wait_time})
        Heading_deviation = self.get_byte_value(str,start_index + 62)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.HDG_DEV,
                       DataParticleKey.VALUE: Heading_deviation})
        Pitch_deviation = self.get_byte_value(str,start_index + 64)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PITCH_DEV,
                       DataParticleKey.VALUE: Pitch_deviation})
        Roll_deviation = self.get_byte_value(str,start_index + 66)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ROLL_DEV,
                       DataParticleKey.VALUE: Roll_deviation})
        Xmit_current = self.get_byte_value(str,start_index + 68)
        Xmit_voltage = self.get_byte_value(str,start_index + 70)
        Ambient_temp = self.get_byte_value(str,start_index + 72)
        Pressure_pos = self.get_byte_value(str,start_index + 74)
        Pressure_neg = self.get_byte_value(str,start_index + 76)
        Attitude_temp = self.get_byte_value(str,start_index + 78)
        Attitude      = self.get_byte_value(str,start_index + 80)
        Contamination_sensor = self.get_byte_value(str,start_index + 82)
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
        status_word = self.get_double_word_value(str,start_index + 84)
        working_list = []
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
        Pressure = self.get_double_word_value(str,start_index + 96)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PRESSURE,
                       DataParticleKey.VALUE: Pressure})
        Pressure_sensor_variance = self.get_double_word_value(str,start_index + 104)
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PRESSURE_VAR,
                       DataParticleKey.VALUE: Pressure_sensor_variance})
        RTCY2K_date_time = [self.get_byte_value(str,start_index + 114),self.get_byte_value(str,start_index + 116),
                            self.get_byte_value(str,start_index + 118),self.get_byte_value(str,start_index + 120),
                            self.get_byte_value(str,start_index + 122),self.get_byte_value(str,start_index + 124),
                            self.get_byte_value(str,start_index + 126),self.get_byte_value(str,start_index + 128)]
        retlist.append({DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.RTCY2K_DATE_TIME,
                       DataParticleKey.VALUE: RTCY2K_date_time})
        return retlist
    
    def parse_velocity_record(self,str,start_index):
        SIZE_OF_CELL_DATA = 16
        templist = []
        local_index = 4   #starting location in header
        for cell_count in range(0,NumCells):
            vel_list = [self.get_signed_word_value(str,start_index + local_index),
                         self.get_signed_word_value(str,start_index + local_index+4),
                         self.get_signed_word_value(str,start_index + local_index+8),
                         self.get_signed_word_value(str,start_index + local_index+12)]
            templist.append(vel_list)
            local_index += SIZE_OF_CELL_DATA
        return templist
    
    def parse_bottom_track_record(self,str,start_index):
        pass    

    def parse_data_record(self,str,start_index):
        SIZE_OF_CELL_DATA = 8
        templist = []
        local_index = 4   #starting location in header
        for cell_count in range(0,NumCells):
            vel_list = [self.get_byte_value(str,start_index + local_index),
                         self.get_byte_value(str,start_index + local_index+2),
                         self.get_byte_value(str,start_index + local_index+4),
                         self.get_byte_value(str,start_index + local_index+6)]
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
        
        result = []
        data_stream = self.raw_data
        num_data_types = self.get_byte_value(data_stream,NUM_DATA_TYPES_INDEX)
        num_bytes_in_ensemble = self.get_word_value(data_stream,NUM_BYTES_IN_ENSEMBLE_INDEX)
        result = [{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.NUM_DATA_TYPES,
                   DataParticleKey.VALUE: num_data_types},
                  {DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.NUM_BYTES_IN_ENSEMBLE,
                  DataParticleKey.VALUE: num_bytes_in_ensemble}]
        
        # calculate checksum over entire ensemble and compare the value to the checksum attached to end of ensemble.
        # assert error if not equal
        num_chars = num_bytes_in_ensemble*2
        try:
            assert self.calc_checksum(data_stream,num_bytes_in_ensemble) == \
                  data_stream[num_chars+2:num_chars+4] + data_stream[num_chars:num_chars+2],\
                  'Checksum error in reading ensemble'
        except AssertionError, args:
            log.error("In build_parsed_values; %s" % str(args))

#       Now look at data in data_types records; use data type offset to point to start of records
#       Use 2-byte IDs in each record to identify type of data record
#       (The only items in an ensemble that exist at fixed offsets are num_data_types, num_bytes_in_ensemble,
#       and the offsets of the data type records.
#       Now build a list of data type records
        for type_cnt in range(0,num_data_types):
            id_offset_addr = type_cnt*WORD_SIZE + DATA_TYPE_LOC_INDEX_BASE
            id_offset = BYTE_SIZE*self.get_word_value(data_stream,id_offset_addr)
            id_value = data_stream[id_offset:id_offset+WORD_SIZE]
            if id_value == FIXED_LEADER_ID:
                result.extend(self.parse_fixed_leader_record(data_stream,id_offset))
            elif id_value == VAR_LEADER_ID:
                result.extend(self.parse_var_leader_record(data_stream,id_offset))
            elif id_value == VELOCITY_ID:
                result.extend([{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.VELOCITY_DATA,
                   DataParticleKey.VALUE: self.parse_velocity_record(data_stream,id_offset)}])
            elif id_value == CORR_MAG_ID:
                result.extend([{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.CORR_MAG_DATA,
                   DataParticleKey.VALUE: self.parse_data_record(data_stream,id_offset)}])
            elif id_value == ECHO_INTENSITY_ID:
                result.extend([{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.ECHO_INTENSITY_DATA,
                   DataParticleKey.VALUE: self.parse_data_record(data_stream,id_offset)}])
            elif id_value == PERCENT_GOOD_ID:
                result.extend([{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PERCENT_GOOD_DATA,
                   DataParticleKey.VALUE: self.parse_data_record(data_stream,id_offset)}])
            elif id_value == STATUS_ID:
                result.extend([{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.STATUS_DATA,
                   DataParticleKey.VALUE: self.parse_data_record(data_stream,id_offset)}])
            elif id_value == PERCENT_GOOD_ID:
                result.extend([{DataParticleKey.VALUE_ID: ADCPT_EnsembleDataParticleKey.PERCENT_GOOD_DATA,
                   DataParticleKey.VALUE: self.parse_data_record(data_stream,id_offset)}])
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
    # Superclass overrides for resource query.
    ########################################################################
    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        log.debug("get_resource_params: parmeter list %s" % Parameter.list())
        
        return Parameter.list()

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
        self._add_build_handler(InstrumentCmds.RETRIEVE_FACTORY_SETUP, self._build_simple_command)
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
        self._add_build_handler(InstrumentCmds.RETRIEVE_FACTORY_SETUP, self._build_simple_command)
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
        self._add_response_handler(InstrumentCmds.DISPLAY_FACTORY_CALIBRATION, self._parse_display_fatory_calibration_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_SYSTEM_CONFIGURATION, self._parse_display_system_configuration_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_TRANSFORMATION_MATRIX, self._parse_display_transformation_matrix_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_FAULT_LOG, self._parse_display_fault_log_response)
        self._add_response_handler(InstrumentCmds.BUILT_IN_TEST, self._parse_built_in_test_response)
        self._add_response_handler(InstrumentCmds.OUTPUT_CALIBRATION_DATA, self._parse_output_calibration_data_response)

        # Add sample handlers.

        # Start state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

    def _build_simple_command(self, cmd):
        """
        Build handler for basic adcpt commands.
        @param cmd the simple adcpt command to format (no value to attach to the command)
        @retval The command to be sent to the device.
        """
        print("$$$$$$$$$$$$$$$$$$$$$$$ build_simple_command: %s" % cmd)
        return cmd + NEWLINE
    
    def _build_set_command(self, cmd, param, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        try:
        try:

            set_cmd = '%s%s' % (cmd,val)
            print("$$$$$$$$$$$$$$$$$$$$$$$ build_set_command: %s" % set_cmd)
        """
        try:
            str_val = self._param_dict.format(param, val)
            set_cmd = '%s%s' % (cmd, str_val)
            set_cmd = set_cmd + NEWLINE
            print("$$$$$$$$$$$$$$$$$$$$$$$ build_set_command: %s" % set_cmd)
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return set_cmd + NEWLINE

    def get_word_value(self,str,index):
        """
        Returns value of a 2-byte word in an ascii-hex string into a decimal integer
        """
        return int(str[index+2:index+4]+str[index:index+2],16)
           
    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        Chunker sieve method to help the chunker identify chunks.
        @returns a list of chunks identified, if any. The chunks are all the same type.
        """
#        print "sieve_function: raw_data is ",raw_data

        sieve_matchers = [ENSEMBLE_REGEX_MATCHER,
                          CALIBRATION_DATA_REGEX_MATCHER,
                          PS0_REGEX_MATCHER,
                          PS3_REGEX_MATCHER,
                          FD_REGEX_MATCHER,
                          PT200_REGEX_MATCHER,
                          BREAK_SUCCESS_REGEX,
                          BREAK_ALARM_REGEX,
                          POWERING_DOWN_REGEX,
                          ERR_REGEX ]

        return_list = []
        for matcher in sieve_matchers:
            if matcher == ENSEMBLE_REGEX_MATCHER:
                start_pos = 0   #starting index in a string for search
                numIDs = raw_data.count(ENSEMBLE_HEADER_ID)    #see how many ensembles to look for
                while numIDs > 0:
                    pos = raw_data.find(ENSEMBLE_HEADER_ID,start_pos)
                    strip = raw_data[pos:]
                    expected_length = 0
                    if len(strip) > ENSEMBLE_LENGTH_LOC+WORD_SIZE:  #make sure you have long-enough string to get the ensemble size
                        ensemble_length_bytes = int(strip[ENSEMBLE_LENGTH_LOC+2:ENSEMBLE_LENGTH_LOC+4] + 
                                                    strip[ENSEMBLE_LENGTH_LOC:ENSEMBLE_LENGTH_LOC+2],16)
                        ensemble_length_chars = BYTE_SIZE*ensemble_length_bytes+WORD_SIZE  #size in header didn't include size of checksum word
                        if len(strip) >= ensemble_length_chars:
                            log.debug("sieve_function got enough data")
                            return_list.append((pos,pos+ensemble_length_chars))
                            start_pos += pos+ensemble_length_chars
                        else:
                            log.debug("sieve_function didn't get enough data")
                    numIDs -= 1
            elif matcher == BREAK_SUCCESS_REGEX:
                pass
            elif matcher == BREAK_ALARM_REGEX:
                pass
            elif matcher == POWERING_DOWN_REGEX:
                pass
            elif matcher == ERR_REGEX:
                pass
            else:   
                for match in matcher.finditer(raw_data):
                    return_list.append((match.start(), match.end()))
                
        return return_list

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        adcpt: not using regex/match lambdas, but keeping them in the calls
        to avoid errors.
        """
        # Add parameter handlers to parameter dict.
        ds_line_01 = r'user info=(.*)$'
                                
        self._param_dict.add(Parameter.TRANSMIT_POWER,
            ds_line_01,
            lambda st: adcpt_cache_dict[Parameter.TRANSMIT_POWER],
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.TRANSMIT_POWER],
            default_value = 255)

        self._param_dict.add(Parameter.SPEED_OF_SOUND,
            ds_line_01,
            lambda st: adcpt_cache_dict[Parameter.SPEED_OF_SOUND],
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.SPEED_OF_SOUND],
            startup_param = True,
            default_value = 1500)

        self._param_dict.add(Parameter.SALINITY,
            ds_line_01,
            lambda st: adcpt_cache_dict[Parameter.SALINITY],
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.SALINITY],
            startup_param = True,
            default_value = 35)

        self._param_dict.add(Parameter.TIME_PER_BURST,
            ds_line_01,
            lambda : adcpt_cache_dict[Parameter.TIME_PER_BURST],
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.TIME_PER_BURST],
            startup_param = True,
            default_value = '00:00:00:00')

        self._param_dict.add(Parameter.ENSEMBLES_PER_BURST,
            ds_line_01,
            lambda : adcpt_cache_dict[Parameter.ENSEMBLES_PER_BURST],
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.ENSEMBLES_PER_BURST],
            startup_param = True,
            default_value = 0)

        self._param_dict.add(Parameter.TIME_PER_ENSEMBLE,
            ds_line_01,
            lambda : adcpt_cache_dict[Parameter.TIME_PER_ENSEMBLE],
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.TIME_PER_ENSEMBLE],
            startup_param = True,
            default_value = '01:00:00:00')

        self._param_dict.add(Parameter.TIME_OF_FIRST_PING,
            ds_line_01,
            lambda : adcpt_cache_dict[Parameter.TIME_OF_FIRST_PING],
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.TIME_OF_FIRST_PING],
            startup_param = True,
            default_value = '00/00/00, 00:00:00')

        self._param_dict.add(Parameter.TIME_OF_FIRST_PING_Y2K,
            ds_line_01,
            lambda : adcpt_cache_dict[Parameter.TIME_OF_FIRST_PING_Y2K],
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.TIME_OF_FIRST_PING_Y2K],
            startup_param = True,
            default_value = '0000/00/00, 00:00:00')

        self._param_dict.add(Parameter.TIME_BETWEEN_PINGS,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.TIME_BETWEEN_PINGS],
            startup_param = True,
            default_value = '01:20:00')

        self._param_dict.add(Parameter.REAL_TIME_CLOCK,
            ds_line_01,
            lambda : adcpt_cache_dict[Parameter.REAL_TIME_CLOCK],
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.REAL_TIME_CLOCK],
            startup_param = True,
            default_value = '00/00/00, 00:00:00')

        self._param_dict.add(Parameter.REAL_TIME_CLOCK_Y2K,
            ds_line_01,
            lambda : adcpt_cache_dict[Parameter.REAL_TIME_CLOCK_Y2K],
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.REAL_TIME_CLOCK_Y2K],
            startup_param = True,
            default_value = '0000/00/00, 00:00:00')

        self._param_dict.add(Parameter.BUFFERED_OUTPUT_PERIOD,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.BUFFERED_OUTPUT_PERIOD],
            startup_param = True,
            default_value = '00:00:00')

        self._param_dict.add(Parameter.FALSE_TARGET_THRESHOLD_MAXIMUM,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.FALSE_TARGET_THRESHOLD_MAXIMUM],
            default_value = 50)

        self._param_dict.add(Parameter.LOW_CORRELATION_THRESHOLD,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.LOW_CORRELATION_THRESHOLD],
            default_value = 64)

        self._param_dict.add(Parameter.ERROR_VELOCITY_THRESHOLD,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.ERROR_VELOCITY_THRESHOLD],
            default_value = 2000)

        self._param_dict.add(Parameter.CLIP_DATA_PAST_BOTTOM,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.CLIP_DATA_PAST_BOTTOM],
            default_value = 0)

        self._param_dict.add(Parameter.RECEIVER_GAIN_SELECT,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.RECEIVER_GAIN_SELECT],
            default_value = 1)

        self._param_dict.add(Parameter.WATER_REFERENCE_LAYER,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.WATER_REFERENCE_LAYER],
            default_value = [1,5])

        self._param_dict.add(Parameter.NUMBER_OF_DEPTH_CELLS,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.NUMBER_OF_DEPTH_CELLS],
            startup_param = True,
            default_value = 30)

        self._param_dict.add(Parameter.PINGS_PER_ENSEMBLE,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.PINGS_PER_ENSEMBLE],
            startup_param = True,
            default_value = 45)

        self._param_dict.add(Parameter.DEPTH_CELL_SIZE,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.DEPTH_CELL_SIZE],
            startup_param = True,
            default_value = 800)

        self._param_dict.add(Parameter.TRANSMIT_LENGTH,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.TRANSMIT_LENGTH],
            startup_param = True,
            default_value = 0)

        self._param_dict.add(Parameter.PING_WEIGHT,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.PING_WEIGHT],
            startup_param = True,
            default_value = 0)

        self._param_dict.add(Parameter.AMBIGUITY_VELOCITY,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.AMBIGUITY_VELOCITY],
            startup_param = True,
            default_value = 175)
            
        self._param_dict.add(Parameter.MODE_1_BANDWIDTH_CONTROL,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.MODE_1_BANDWIDTH_CONTROL],
            startup_param = False,
            default_value = 1,
            visibility=ParameterDictVisibility.READ_ONLY)
            
        self._param_dict.add(Parameter.BLANK_AFTER_TRANSMIT,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.BLANK_AFTER_TRANSMIT],
            startup_param = True,
            default_value = 352,
            visibility=ParameterDictVisibility.READ_ONLY)
            
        self._param_dict.add(Parameter.DATA_OUT,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.DATA_OUT],
            startup_param = True,
            default_value = 111100000,
            visibility=ParameterDictVisibility.READ_ONLY)
            
        self._param_dict.add(Parameter.INSTRUMENT_ID,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.INSTRUMENT_ID],
            startup_param = True,
            default_value = 0,
            visibility=ParameterDictVisibility.READ_ONLY)
            
        self._param_dict.add(Parameter.WATER_PROFILING_MODE,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            value = adcpt_cache_dict[Parameter.WATER_PROFILING_MODE],
            startup_param = True,
            default_value = 1,
            visibility=ParameterDictVisibility.READ_ONLY)

            
        local_dict = self._param_dict.get_config()
#        log.debug("&&&&&&&&&&&&& _build_param_dict: _param_dict: %s" % local_dict)
#        log.debug("^^^^^^^^^^^^^  at same time the adcpt_cache_dict is %s" % adcpt_cache_dict)
         
    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Send a CE (send last data ensemble) command
        to the adcpt; this causes the chunker to extract last data and put in adcpt_cache_dict.
        Then calling _build_param_dict() causes the new data to be updated in param dict.
        """
        print "!!!!!!!!!!!!!!!!!!!! Got to update_params"
        # Get old param dict config.
        old_config = self._param_dict.get_config()

        # Issue display commands and parse results.
        
        ### adcpt--send CE command to get last ensemble (wait for response)
        ### adcpt--make sure ensemble goes through parser!!
        ### adcpt--ok to leave new values in cache?? Steve F. says inefficient to call
        ###    _build_param_dict every time.
        self._do_cmd_no_resp(InstrumentCmds.SEND_LAST_DATA_ENSEMBLE)
        
        self._build_param_dict()

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    @staticmethod
    def _string_to_string(v):
        return v

    def _got_chunk(self, chunk):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        if(self._extract_sample(ADCPT_EnsembleDataParticle, ENSEMBLE_REGEX_MATCHER, chunk)):
            log.debug("_got_chunk = Passed good")
        else:
            log.debug("_got_chunk = Failed")

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    ########################################################################
    # response handlers.
    ########################################################################
    def _parse_display_system_configuration_response(self,*args,**kwargs):
        pass
    def _parse_display_transformation_matrix_response(self,*args,**kwargs):
        pass
    def _parse_display_fault_log_response(self,*args,**kwargs):
        pass
    def _parse_built_in_test_response(self,*args,**kwargs):
        pass
    def _parse_output_calibration_data_response(self,*args,**kwargs):
        pass
    def _parse_display_fatory_calibration_response(self,*args,**kwargs):
        pass


    ########################################################################
    # Unknown handlers.
    ########################################################################
    def _handler_unknown_break_success(self, *args, **kwargs):
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_unknown_break_success"
        next_state = ProtocolState.COMMAND
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        return(next_state)

    def _handler_unknown_break_alarm(self, *args, **kwargs):
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_unknown_break_alarm"
        next_state = None
        return(next_state)

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_unknown_enter"
        
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_unknown_exit"

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
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_unknown_discover"

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
                    InstrumentCmds.COMM_PARAMS_DEFAULT,
                    InstrumentCmds.RETRIEVE_FACTORY_SETUP]
    
    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_command_enter"

        instrument_setup_cmds = [
            InstrumentCmds.RETRIEVE_FACTORY_SETUP,
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
            InstrumentCmds.AMBIGUITY_VELOCITY_DEFAULT    ]
        
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
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_command_get"
        next_state = ProtocolState.COMMAND
        self._build_param_dict()     #make sure data is up-to-date
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

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter       
         """
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_command_set"

        params_to_cmds = {
      #      InstrumentCmds.SET_COMM_PARAMS,
      #      InstrumentCmds.SET_COLLECTION_MODE,

            'TRANSMIT_POWER' : InstrumentCmds.SET_TRANSMIT_POWER,
            'SPEED_OF_SOUND' : InstrumentCmds.SET_SPEED_OF_SOUND,
            'SALINITY' : InstrumentCmds.SET_SALINITY,
            'TIME_PER_BURST' : InstrumentCmds.SET_TIME_PER_BURST,
            'ENSEMBLES_PER_BURST' : InstrumentCmds.SET_ENSEMBLES_PER_BURST,
            'TIME_PER_ENSEMBLE' : InstrumentCmds.SET_TIME_PER_ENSEMBLE,
            'TIME_OF_FIRST_PING' : InstrumentCmds.SET_TIME_OF_FIRST_PING,
            'TIME_OF_FIRST_PING_Y2K' : InstrumentCmds.SET_TIME_OF_FIRST_PING_Y2K,
            'TIME_BETWEEN_PINGS' : InstrumentCmds.SET_TIME_BETWEEN_PINGS,
            'REAL_TIME_CLOCK' : InstrumentCmds.SET_REAL_TIME_CLOCK,
            'REAL_TIME_CLOCK_Y2K' : InstrumentCmds.SET_REAL_TIME_CLOCK_Y2K,
            'BUFFERED_OUTPUT_PERIOD' : InstrumentCmds.SET_BUFFERED_OUTPUT_PERIOD,
            'FALSE_TARGET_THRESHOLD_MAXIMUM' : InstrumentCmds.SET_FALSE_TARGET_THRESHOLD_MAXIMUM,
            'LOW_CORRELATION_THRESHOLD' : InstrumentCmds.SET_LOW_CORRELATION_THRESHOLD,
            'ERROR_VELOCITY_THRESHOLD' : InstrumentCmds.SET_ERROR_VELOCITY_THRESHOLD,
            'CLIP_DATA_PAST_BOTTOM' : InstrumentCmds.SET_CLIP_DATA_PAST_BOTTOM,
            'RECEIVER_GAIN_SELECT' : InstrumentCmds.SET_RECEIVER_GAIN_SELECT,
            'WATER_REFERENCE_LAYER' : InstrumentCmds.SET_WATER_REFERENCE_LAYER,
            'NUMBER_OF_DEPTH_CELLS' : InstrumentCmds.SET_NUMBER_OF_DEPTH_CELLS,
            'PINGS_PER_ENSEMBLE' : InstrumentCmds.SET_PINGS_PER_ENSEMBLE,
            'DEPTH_CELL_SIZE' : InstrumentCmds.SET_DEPTH_CELL_SIZE,
            'TRANSMIT_LENGTH' : InstrumentCmds.SET_TRANSMIT_LENGTH,
            'PING_WEIGHT' : InstrumentCmds.SET_PING_WEIGHT,
            'AMBIGUITY_VELOCITY' : InstrumentCmds.SET_AMBIGUITY_VELOCITY,
            'MODE_1_BANDWIDTH_CONTROL' : InstrumentCmds.SET_MODE_1_BANDWIDTH_CONTROL,
            'BLANK_AFTER_TRANSMIT' : InstrumentCmds.SET_BLANK_AFTER_TRANSMIT,
            'DATA_OUT' : InstrumentCmds.SET_DATA_OUT,
            'INSTRUMENT_ID' : InstrumentCmds.SET_INSTRUMENT_ID,
            'WATER_PROFILING_MODE' : InstrumentCmds.SET_WATER_PROFILING_MODE
            
        }
         
        """
            # if input command == 'DEPLOY', set up for state change 
            # generate an event for go-to-deployment
            # next_state = ProtocolState.AUTOSAMPLE
        """
#$$$$$$$$$$$$$$$$$$$$$
        next_state = None
        result = None
        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
        try:
            params = args[0]
            log.debug("######### params = " + str(repr(params)))
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        else:
#            for (key, val) in params_to_cmds.iteritems():
#                log.debug("KEY = " + str(key) + " VALUE = " + str(val))
 
            for (key, val) in params.iteritems():
                log.debug("KEY = " + str(key) + " VALUE = " + str(val))
                print"&&&&&&&&&&&&&&&&&&& handler_command_set: arguments to do_cmd etc are ",params_to_cmds[key],key,val
                result = self._do_cmd_no_resp(params_to_cmds[key], key, str(val), **kwargs)
                log.debug("**********************RESULT************* = " + str(result))

        return (next_state, result)
#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

    def _handler_command_self_deploy(self, *args, **kwargs):
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_autosample_self_deploy"
        next_state = ProtocolState.AUTOSAMPLE
        return(next_state)

    def _handler_command_start_autosample(self, *args, **kwargs):
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_command_start_autosample"
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        result = None
        return (next_state, (next_agent_state, result)) 

    def _handler_command_quit_session(self, *args, **kwargs):
        """
        Power-down the instrument when sent a QUIT_SESSION event.
        'CZ' is the adcpt command to power down.
        """
        next_state = None

        result = self._do_cmd_no_resp(InstrumentCmds.POWER_DOWN, *args, **kwargs)
        return (next_state, result)

    def _handler_command_exit(self, *args, **kwargs):
        global command_set_cmds
        # send the commands that accumulated during 'execute'
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_command_exit"

        final_before_deploy_cmds = [
            InstrumentCmds.SAVE_SETUP_TO_RAM,
            InstrumentCmds.START_DEPLOYMENT ]
        
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
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_command_powering_down"
        next_state = ProtocolState.UNKNOWN
        return(next_state)

    ########################################################################
    # Autosample handlers.
    ########################################################################
    def _handler_autosample_exit(self,*args,**kwargs):
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_autosample_exit"


    def _handler_autosample_enter(self,*args,**kwargs):
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_autosample_enter"
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
    
    def _handler_autosample_break_success(self, *args, **kwargs):
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_autosample_break_success"
        next_state = ProtocolState.COMMAND
        return(next_state)


    def _handler_autosample_break_alarm(self, *args, **kwargs):
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_autosample_break_alarm"



    def _handler_autosample_get(self, *args, **kwargs):
        print"^^^^^^^^^^^^^^^^^^ FSM_TRACKER: in _handler_autosample_get"

        self._build_param_dict()     #make sure data is up-to-date
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

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        pass


