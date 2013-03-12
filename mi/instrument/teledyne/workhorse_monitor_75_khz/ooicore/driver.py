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
from mi.core.exceptions import InstrumentStateException
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
    EXPERT_ON = 'EXPERTON'
    EXPERT_OFF = 'EXPERTOFF'
    LIST_FIRMWARE_UPGRADES = 'OL'
    OUTPUT_CALIBRATION_DATA = 'AC'
    OUTPUT_FACTORY_CALIBRATION_DATA = 'AD' #NEED#
    FIELD_CALIBRATE_COMPAS = 'AF'
    LOAD_FACTORY_CALIBRATION = 'AR'
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
    TIME = 'TT'                    # 2013/02/26,05:28:23 (CCYY/MM/DD,hh:mm:ss)

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
    ACQUIRE_STATUS = 'acquire_status'
    CALIBRATION_COEFFICIENTS = 'calibration_coefficients'
    CLOCK_SYNC = 'clock_sync'

###############################################################################
# Data Particles
###############################################################################

class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW
    PT200_PARSED = 'pt200_parsed'
    PS3_PARSED = 'ps3_parsed'
    PS0_PARSED = 'ps0_parsed'

    #ENSEMBLE_PARSED = 'ensemble_parsed'
    #CALIBRATION_PARSED = 'calibration_parsed'
    #FD_PARSED = 'fd_parsed'


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
        self._add_build_handler(InstrumentCmds.ZERO_PRESSURE_READING,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.EXPERT_ON,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.EXPERT_OFF,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.LIST_FIRMWARE_UPGRADES,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.OUTPUT_CALIBRATION_DATA,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.OUTPUT_FACTORY_CALIBRATION_DATA,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.FIELD_CALIBRATE_COMPAS,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.LOAD_FACTORY_CALIBRATION, 
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.CHOOSE_EXTERNAL_DEVICES,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SEND_LAST_DATA_ENSEMBLE,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SAVE_SETUP_TO_RAM,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.RETRIEVE_PARAMETERS,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.START_DEPLOYMENT,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.CLEAR_ERROR_STATUS_WORD,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_ERROR_STATUS_WORD,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.POWER_DOWN,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.LOAD_SPEED_OF_SOUND,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GO_RAW_MODE,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GO_REAL_MODE,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GET_SINGLE_SCAN,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.CLEAR_FAULT_LOG,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_FAULT_LOG,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.TOGGLE_FAULT_LOG_DEBUG,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.RUN_PRE_DEPLOYMENT_TESTS,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.RUN_BEAM_CONTINUITY_TEST,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SHOW_HEADING_PITCH_ROLL_ORIENTATION_TEST_RESULTS,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GET_SYSTEM_CONFIGURATION,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX,
                                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.RUN_TEST,
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
        self._add_response_handler(InstrumentCmds.ZERO_PRESSURE_READING,
                                self._parse_zero_pressure_reading_response)
        self._add_response_handler(InstrumentCmds.EXPERT_ON,
                                self._parse_expert_on_response)
        self._add_response_handler(InstrumentCmds.EXPERT_OFF,
                                self._parse_expert_off_response)
        self._add_response_handler(InstrumentCmds.LIST_FIRMWARE_UPGRADES,
                                self._parse_list_firmware_upgrades_response)
        self._add_response_handler(InstrumentCmds.OUTPUT_CALIBRATION_DATA,
                                self._parse_output_calibration_data_response)
        self._add_response_handler(InstrumentCmds.OUTPUT_FACTORY_CALIBRATION_DATA,
                                self._parse_output_factory_calibration_data_response)
        self._add_response_handler(InstrumentCmds.FIELD_CALIBRATE_COMPAS,
                                self._parse_field_calibrate_compas_response)
        self._add_response_handler(InstrumentCmds.LOAD_FACTORY_CALIBRATION,
                                self._parse_load_factory_calibration_response)
        self._add_response_handler(InstrumentCmds.CHOOSE_EXTERNAL_DEVICES,
                                self._parse_choose_external_devices_response)
        self._add_response_handler(InstrumentCmds.SEND_LAST_DATA_ENSEMBLE,
                                self._parse_send_last_data_ensemble_response)
        self._add_response_handler(InstrumentCmds.SAVE_SETUP_TO_RAM,
                                self._parse_save_setup_to_ram_response)
        self._add_response_handler(InstrumentCmds.RETRIEVE_PARAMETERS,
                                self._parse_retrieve_parameters_response)
        self._add_response_handler(InstrumentCmds.START_DEPLOYMENT,
                                self._parse_start_deployment_response)
        self._add_response_handler(InstrumentCmds.CLEAR_ERROR_STATUS_WORD,
                                self._parse_clear_error_status_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_ERROR_STATUS_WORD,
                                self._parse_error_status_response)
        self._add_response_handler(InstrumentCmds.POWER_DOWN,
                                self._parse_power_down_response)
        self._add_response_handler(InstrumentCmds.LOAD_SPEED_OF_SOUND,
                                self._parse_load_speed_of_sound_response)
        self._add_response_handler(InstrumentCmds.GO_RAW_MODE,
                                self._parse_raw_mode_response)
        self._add_response_handler(InstrumentCmds.GO_REAL_MODE,
                                self._parse_real_mode_response)
        self._add_response_handler(InstrumentCmds.GET_SINGLE_SCAN,
                                self._parse_single_scan_response)
        self._add_response_handler(InstrumentCmds.CLEAR_FAULT_LOG,
                                self._parse_clear_fault_log_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_FAULT_LOG,
                                self._parse_fault_log_response)
        self._add_response_handler(InstrumentCmds.TOGGLE_FAULT_LOG_DEBUG,
                                self._parse_fault_log_toggle_response)
        self._add_response_handler(InstrumentCmds.RUN_PRE_DEPLOYMENT_TESTS,
                                self._parse_depolyment_tests)
        self._add_response_handler(InstrumentCmds.RUN_BEAM_CONTINUITY_TEST,
                                self._parse_beam_continuity_test)
        self._add_response_handler(InstrumentCmds.SHOW_HEADING_PITCH_ROLL_ORIENTATION_TEST_RESULTS,
                                self._parse_heading_pitch_roll_orientation_test_results)
        self._add_response_handler(InstrumentCmds.GET_SYSTEM_CONFIGURATION,
                                self._parse_system_configuration_response)
        self._add_response_handler(InstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX,
                                self._parse_instrument_transform_matrix_response)
        self._add_response_handler(InstrumentCmds.RUN_TEST,
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

        self._chunker = StringChunker(Protocol.sieve_function)

        self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS,
                                  ProtocolEvent.ACQUIRE_STATUS)
        self._add_scheduler_event(ScheduledJob.CALIBRATION_COEFFICIENTS,
                                  ProtocolEvent.ACQUIRE_CONFIGURATION)
        self._add_scheduler_event(ScheduledJob.CLOCK_SYNC,
                                  ProtocolEvent.SCHEDULED_CLOCK_SYNC)

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
        sieve_matchers = [PT200_REGEX_MATCHER,
                          PS0_REGEX_MATCHER,
                          PS3_REGEX_MATCHER,]

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

        if (self._extract_sample(ADCPT_PT200DataParticle,
                                 PT200_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("successful extract_sample for PT200")
            return

        if (self._extract_sample(ADCPT_PS0DataParticle,
                                 PS0_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("successful extract_sample for PS0")
            return

        if (self._extract_sample(ADCPT_PS3DataParticle,
                                 PS3_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("successful extract_sample for PS3")
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
                log.debug("RETURNING 0")
                return 0
            else:
                log.debug("RETURNING 1")
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
        log.debug("IN _datetime_with_milis_to_time_string_with_milis")
        if not isinstance(v, datetime):
            raise InstrumentParameterException('Value %s is not a datetime.' % v)
        else:
            return datetime.strftime(v, '%H:%M:%S.%f')

    @staticmethod
    def _datetime_to_TT_datetime_string(v):
        """
        Write a datetime string value to string.
        @param v a datetime string val.
        @retval a time with date string formatted.
        @throws InstrumentParameterException if value is not a datetime.
        """

        if not isinstance(v, str):
            raise InstrumentParameterException('Value %s is not a datetime.' % v)
        else:
            return time.strftime("%Y/%m/%d,%H:%M:%S", time.strptime(v, "%d %b %Y  %H:%M:%S"))

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