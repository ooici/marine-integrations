"""
@package mi.instrument.teledyne.workhorse_monitor_75_khz.cgsn.driver
@file marine-integrations/mi/instrument/teledyne/workhorse_monitor_75_khz/cgsn/driver.py
@author Roger Unwin
@brief Driver for the cgsn
Release notes:

moving to teledyne
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

from struct import *
import re
import time as time
import string
import ntplib
import datetime as dt
from mi.core.time import get_timestamp_delayed

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

from mi.core.exceptions import SampleException

# TODO: bring this code back in before delivery.
from mi.instrument.teledyne.workhorse_monitor_75_khz.particles import *



import socket


# default timeout.
TIMEOUT = 10

class InstrumentCmds(BaseEnum):
    """
    Device specific commands
    Represents the commands the driver implements and the string that
    must be sent to the instrument to execute the command.
    """

    BREAK = 'break 500'
    SEND_LAST_SAMPLE = 'CE'
    SAVE_SETUP_TO_RAM = 'CK'
    START_DEPLOYMENT = 'CS'
    OUTPUT_CALIBRATION_DATA = 'AC'
    CLEAR_ERROR_STATUS_WORD = 'CY0'         # May combine with next
    DISPLAY_ERROR_STATUS_WORD = 'CY1'       # May combine with prior
    CLEAR_FAULT_LOG = 'FC'
    GET_FAULT_LOG = 'FD'
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



class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """

    DISCOVER = DriverEvent.DISCOVER
    
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT

    GET_CALIBRATION = "PROTOCOL_EVENT_GET_CALIBRATION"
    GET_CONFIGURATION = "PROTOCOL_EVENT_GET_CONFIGURATION"
    SEND_LAST_SAMPLE = "PROTOCOL_EVENT_SEND_LAST_SAMPLE"

    SAVE_SETUP_TO_RAM = "PROTOCOL_EVENT_SAVE_SETUP_TO_RAM"

    GET_ERROR_STATUS_WORD = "PROTOCOL_EVENT_GET_ERROR_STATUS_WORD"
    CLEAR_ERROR_STATUS_WORD = "PROTOCOL_EVENT_CLEAR_ERROR_STATUS_WORD"

    GET_FAULT_LOG = "PROTOCOL_EVENT_GET_FAULT_LOG"
    CLEAR_FAULT_LOG = "PROTOCOL_EVENT_CLEAR_FAULT_LOG"

    GET_INSTRUMENT_TRANSFORM_MATRIX = "PROTOCOL_EVENT_GET_INSTRUMENT_TRANSFORM_MATRIX"
    RUN_TEST_200 = "PROTOCOL_EVENT_RUN_TEST_200"

    GET = DriverEvent.GET
    SET = DriverEvent.SET

    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT

    PING_DRIVER = DriverEvent.PING_DRIVER

    # Different event because we don't want to expose this as a capability
    SCHEDULED_CLOCK_SYNC = 'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC'
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC

    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    DISCOVER = DriverEvent.DISCOVER

    GET_CALIBRATION = ProtocolEvent.GET_CALIBRATION
    GET_CONFIGURATION = ProtocolEvent.GET_CONFIGURATION
    SEND_LAST_SAMPLE = ProtocolEvent.SEND_LAST_SAMPLE

    SAVE_SETUP_TO_RAM = ProtocolEvent.SAVE_SETUP_TO_RAM

    GET_ERROR_STATUS_WORD = ProtocolEvent.GET_ERROR_STATUS_WORD
    CLEAR_ERROR_STATUS_WORD = ProtocolEvent.CLEAR_ERROR_STATUS_WORD

    GET_FAULT_LOG = ProtocolEvent.GET_FAULT_LOG
    CLEAR_FAULT_LOG = ProtocolEvent.CLEAR_FAULT_LOG

    GET_INSTRUMENT_TRANSFORM_MATRIX = ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX
    RUN_TEST_200 = ProtocolEvent.RUN_TEST_200

    GET = DriverEvent.GET
    SET = DriverEvent.SET

    PING_DRIVER = ProtocolEvent.PING_DRIVER

    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC

    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE




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
    COORDINATE_TRANSFORMATION = 'EX'    #
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
    CLOCK_SYNC = 'clock_sync'
    GET_CONFIGURATION = 'acquire_configuration'
    GET_CALIBRATION = 'acquire_calibration'
###############################################################################
# Driver
###############################################################################

class TeledyneInstrumentDriver(ADCPInstrumentDriver):
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
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_command_clock_sync)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_CALIBRATION, self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_CONFIGURATION, self._handler_command_acquire_configuration)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SAVE_SETUP_TO_RAM, self._handler_command_save_setup_to_ram)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SEND_LAST_SAMPLE, self._handler_command_send_last_sample)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, self._handler_command_get_instrument_transform_matrix)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.RUN_TEST_200, self._handler_command_run_test_200)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_ERROR_STATUS_WORD, self._handler_command_acquire_error_status_word)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLEAR_ERROR_STATUS_WORD, self._handler_command_clear_error_status_word)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLEAR_FAULT_LOG, self._handler_command_clear_fault_log)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_FAULT_LOG, self._handler_command_display_fault_log)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        #
        # These will need a handful of shared functions to stage the 
        # parameters to the commands
        #

        self._add_build_handler(InstrumentCmds.BREAK, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.OUTPUT_CALIBRATION_DATA, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SEND_LAST_SAMPLE, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SAVE_SETUP_TO_RAM, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.START_DEPLOYMENT, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_ERROR_STATUS_WORD, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.CLEAR_ERROR_STATUS_WORD, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.CLEAR_FAULT_LOG, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GET_FAULT_LOG, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GET_SYSTEM_CONFIGURATION, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.RUN_TEST_200, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SET, self._build_set_command)
        self._add_build_handler(InstrumentCmds.GET, self._build_get_command)

        #
        # Response handlers
        #
        self._add_response_handler(InstrumentCmds.BREAK, self._parse_break_response)
        self._add_response_handler(InstrumentCmds.OUTPUT_CALIBRATION_DATA, self._parse_output_calibration_data_response)
        self._add_response_handler(InstrumentCmds.SEND_LAST_SAMPLE, self._parse_send_last_sample_response)
        self._add_response_handler(InstrumentCmds.SAVE_SETUP_TO_RAM, self._parse_save_setup_to_ram_response)
        self._add_response_handler(InstrumentCmds.START_DEPLOYMENT, self._parse_start_deployment_response)
        self._add_response_handler(InstrumentCmds.CLEAR_ERROR_STATUS_WORD, self._parse_clear_error_status_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_ERROR_STATUS_WORD, self._parse_error_status_response)
        self._add_response_handler(InstrumentCmds.CLEAR_FAULT_LOG, self._parse_clear_fault_log_response)
        self._add_response_handler(InstrumentCmds.GET_FAULT_LOG, self._parse_fault_log_response)
        self._add_response_handler(InstrumentCmds.GET_SYSTEM_CONFIGURATION, self._parse_system_configuration_response)
        self._add_response_handler(InstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX, self._parse_instrument_transform_matrix_response)
        self._add_response_handler(InstrumentCmds.RUN_TEST_200, self._parse_test_response)
        self._add_response_handler(InstrumentCmds.SET, self._parse_set_response)
        self._add_response_handler(InstrumentCmds.GET, self._parse_get_response)


        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be
        # filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(TeledyneProtocol.sieve_function)

        self._add_scheduler_event(ScheduledJob.GET_CONFIGURATION, ProtocolEvent.GET_CONFIGURATION)
        self._add_scheduler_event(ScheduledJob.GET_CALIBRATION, ProtocolEvent.GET_CALIBRATION)
        self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.SCHEDULED_CLOCK_SYNC)

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
                    #log.debug("LEN IS = %s", str(l[0]))
                    outer_pos = match.start()
                    #log.debug("MATCH START = " + str(outer_pos))
                    ADCP_PD0_PARSED_TRUE_MATCHER = re.compile(r'\x7f\x7f(.{' + str(l[0]) + '})', re.DOTALL)

                    for match in ADCP_PD0_PARSED_TRUE_MATCHER.finditer(raw_data, outer_pos):
                        inner_pos = match.start()
                        #log.debug("INNER MATCH START = " + str(inner_pos))
                        if (outer_pos == inner_pos):
                            log.debug("MATCHED!!!!! %d .. %d", match.start(), match.end())
                            return_list.append((match.start(), match.end()))
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
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True,
            direct_access=False,
            visibility=ParameterDictVisibility.READ_ONLY,
            default_value='11110')

        self._param_dict.add(Parameter.BANNER,
            r'CH = (\d) \-+ Suppress Banner',
            lambda match:  bool(int(match.group(1), base=10)), # not
            self._bool_to_int, # _reverse_bool_to_int
            startup_param=True,
            default_value=True)

        self._param_dict.add(Parameter.INSTRUMENT_ID,
            r'CI = (\d+) \-+ Instrument ID ',
            lambda match: int(match.group(1), base=10),
            self._int_to_string,
            startup_param=True,
            default_value=0)

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

        self._param_dict.add(Parameter.COORDINATE_TRANSFORMATION,
            r'EX = (\d+) \-+ Coord Transform ',
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True,
            default_value='00111')

        self._param_dict.add(Parameter.SENSOR_SOURCE,
            r'EZ = (\d+) \-+ Sensor Source ',
            lambda match: str(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.TIME_PER_ENSEMBLE,
            r'TE (\d\d:\d\d:\d\d.\d\d) \-+ Time per Ensemble ',
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True,
            default_value='00:00:00.00')

        self._param_dict.add(Parameter.TIME_OF_FIRST_PING,
            r'TG (..../../..,..:..:..) - Time of First Ping ',
            lambda match: str(match.group(1)),
            self._string_to_string) #,
            #startup_param=True,
            #default_value='****/**/**,**:**:**')

        self._param_dict.add(Parameter.TIME_PER_PING,
            r'TP (\d\d:\d\d.\d\d) \-+ Time per Ping',
            lambda match: str(match.group(1)),
            self._string_to_string,
            startup_param=True,
            default_value='00:01.00')

        self._param_dict.add(Parameter.TIME,
            r'TT (\d\d\d\d/\d\d/\d\d,\d\d:\d\d:\d\d) \- Time Set ',
            lambda match: str(match.group(1)),
            self._string_to_string,
            visibility=ParameterDictVisibility.READ_ONLY)

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
            lambda match: str(match.group(1)),
            self._string_to_string,
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

        #logging = self._is_logging()

        # If we are in streaming mode and our configuration on the
        # instrument matches what we think it should be then we
        # don't need to do anything.
        if(not self._instrument_config_dirty()):
            return True

        error = None

        try:
            """
            if(logging):
                # Switch to command mode,
                self._stop_logging()
            """
            self._apply_params()

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            """
            if(logging):
                self._start_logging()
            """
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
        #self._do_cmd_resp(InstrumentCmds.DISPLAY_CALIBRATION)
        self._update_params()

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

    def _send_break(self):
        """
        Send a BREAK to attempt to wake the device.
        """
        log.debug("IN _send_break")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error, msg:
            log.debug("WHOOPS! 1")

        try:
            sock.connect(('10.180.80.178', 2102))
        except socket.error, msg:
            log.debug("WHOOPS! 2")
        sock.send("break 300\r\n")
        sock.close()

    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the device.
        """
        log.debug("IN _send_wakeup DISABLED. is it really needed?")

        #self._connection.send(NEWLINE)

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. 
        """

        #prompt = self._wakeup(timeout=TIMEOUT, delay=0.3)

        # Get old param dict config.
        log.debug("IN _update_params" + str(args) + str(kwargs))
        old_config = self._param_dict.get_config()
        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.

        kwargs['expected_prompt'] = Prompt.COMMAND + NEWLINE + Prompt.COMMAND
        kwargs['timeout'] = 0  # TODO: may want to remove this...
        cmds = dir(Parameter)
        results = ""
        log.debug("CMDS = %s", str(cmds))
        for attr in sorted(cmds):
            log.debug("attr = %s",str(attr))
            if attr not in ['dict', 'has', 'list', 'ALL']:
                if not attr.startswith("_"):
                    key = getattr(Parameter, attr)
                    #kwargs['expected_prompt'] = "[" + NEWLINE + Prompt.COMMAND + "]+"
                    result = self._do_cmd_resp(InstrumentCmds.GET, key, **kwargs)
                    results += result + NEWLINE

        new_config = self._param_dict.get_config()
        # Issue display commands and parse results.

        log.debug("**********************************")
        log.debug("OLD_CONFIG = " + repr(old_config))
        log.debug("NEW_CONFIG = " + repr(new_config))
        log.debug("**********************************")

        # We ignore the data time parameter diffs [taken from sbe16plus_v2 driver]
        #new_config[Parameter.TIME] = old_config.get(Parameter.TIME)

        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

        return results

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
        x
        """

    def _parse_output_calibration_data_response(self, response, prompt):
        """
        x
        """
        log.debug("parse_output_calibration_data_response = %s", str(response))
        return response

    def _parse_send_last_sample_response(self, response, prompt):
        """
        get the response from the CE command.  
        Remove the >\n> from the end of it.
        """

        response = re.sub("CE\r\n", "", response)
        log.debug("RESPONSE = " + response)
        return (True, response)

    def _parse_save_setup_to_ram_response(self, response, prompt):
        """
        save settings to nv ram. return response.
        """

        # Cleanup teh results
        response = re.sub("CK\r\n", "", response)
        response = re.sub("\[", "", response)
        response = re.sub("\]", "", response)
        response = re.sub("\r\n>", "", response)
        return (True, response)

    def _parse_start_deployment_response(self, response, prompt):
        """
        response is CS echoed back then sample.  we can live without returning that.
        """

        pass

    def _parse_clear_error_status_response(self, response, prompt):
        """
        x
        """
        log.debug("parse_error_status_response = %s", str(response))
        response = re.sub("CY0\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return (True, response)

    def _parse_error_status_response(self, response, prompt):
        """
        get the error status word, it should be 8 bytes of hexidecimal.
        """

        log.debug("parse_error_status_response = %s", str(response))
        response = re.sub("CY1\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return (True, response)

    def _parse_clear_fault_log_response(self, response, prompt):
        """
        clear the fault log.
        """
        response = re.sub("FC\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return (True, response)

    def _parse_fault_log_response(self, response, prompt):
        """
        display the fault log.
        """
        response = re.sub("FD\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return (True, response)

    def _parse_system_configuration_response(self, response, prompt):
        """
        x
        """

    def _parse_instrument_transform_matrix_response(self, response, prompt):
        """
        display the fault log.
        """
        response = re.sub("PS3\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return (True, response)

    def _parse_test_response(self, response, prompt):
        """
        display the fault log.
        """
        response = re.sub("PT200\r\n\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return (True, response)


    ########################################################################
    # handlers.
    ########################################################################

    def _handler_command_run_test_200(self, *args, **kwargs):
        """
        run test PT200
        """
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.RUN_TEST_200, *args, **kwargs)

        #return (next_state, (next_agent_state, result))
        return (next_state, result)

    def _handler_command_get_instrument_transform_matrix(self, *args, **kwargs):
        """
        save setup to ram.
        """
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX, *args, **kwargs)

        #return (next_state, (next_agent_state, result))
        return (next_state, result)

    def _handler_command_save_setup_to_ram(self, *args, **kwargs):
        """
        save setup to ram.
        """
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.SAVE_SETUP_TO_RAM, *args, **kwargs)

        #return (next_state, (next_agent_state, result))
        return (next_state, result)


    def _handler_command_clear_error_status_word(self, *args, **kwargs):
        """
        clear the error status word
        """
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.CLEAR_ERROR_STATUS_WORD, *args, **kwargs)
        return (next_state, result)

    def _handler_command_acquire_error_status_word(self, *args, **kwargs):
        """
        read the error status word
        """
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.DISPLAY_ERROR_STATUS_WORD, *args, **kwargs)
        return (next_state, result)

    def _handler_command_display_fault_log(self, *args, **kwargs):
        """
        display the error log.
        """
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.GET_FAULT_LOG, *args, **kwargs)
        return (next_state, result)

    def _handler_command_clear_fault_log(self, *args, **kwargs):
        """
        clear the error log.
        """
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.CLEAR_FAULT_LOG, *args, **kwargs)
        return (next_state, result)

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.

        log.debug("*** IN _handler_command_enter(), updating params")
        self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        """

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        """

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result), (ProtocolState.COMMAND or
        State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """
        timeout = kwargs.get('timeout', TIMEOUT)

        log.debug("_handler_unknown_discover");
        next_state = None
        next_agent_state = None

        logging = False  # TODO: implement an actual test.
        log.debug("RIGGING discover to go to COMMAND STATE.")
        prompt = self._send_break()
        if(logging == None):
            raise InstrumentProtocolException('_handler_unknown_discover - unable to to determine state')

        elif(logging):
            next_state = ProtocolState.AUTOSAMPLE
            next_agent_state = ResourceAgentState.STREAMING

        else:
            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.IDLE

        return (next_state, next_agent_state)

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
        log.debug("%%% IN _handler_autosample_exit")

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

        log.info("SYNCING TIME WITH SENSOR")
        self._do_cmd_resp(InstrumentCmds.SET, Parameter.TIME, get_timestamp_delayed("%Y/%m/%d, %H:%M:%S"), **kwargs)

        # Save setup to nvram and switch to autosample if successful.
        self._do_cmd_resp(InstrumentCmds.SAVE_SETUP_TO_RAM, *args, **kwargs)
        # Issue start command and switch to autosample if successful.
        self._do_cmd_resp(InstrumentCmds.START_DEPLOYMENT, *args, **kwargs)

        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING
        result = None

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
        #self._wakeup_until(timeout, Prompt.AUTOSAMPLE)

        #self._stop_logging(timeout)
        prompt = self._send_break()
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
            #self._stop_logging()

            # Sync the clock
            timeout = kwargs.get('timeout', TIMEOUT)
            self._sync_clock(Parameter.TIME, Prompt.COMMAND, timeout, time_format="%Y/%m/%dT, %H:%M:%S")

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
        startup = False

        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('_handler_command_set Set command requires a parameter dict.')

        try:
            startup = args[1]
        except IndexError:
            pass

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        else:
            self._set_params(params, startup)

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
            params = args[0]
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

            for (key, val) in params.iteritems():
                if key in readonly:
                    raise InstrumentParameterException("Attempt to set read only parameter (%s)" % key)

        for (key, val) in params.iteritems():
            log.debug("KEY = " + str(key) + " VALUE = " + str(val))
            result = self._do_cmd_resp(InstrumentCmds.SET, key, val, **kwargs)

        self._update_params()

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        log.debug("IN _handler_command_acquire_status - DOING NOTHING I GUESS")
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 30

        result = self._do_cmd_resp(InstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)
        return (next_state, (next_agent_state, result))

    def _handler_command_acquire_configuration(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 120  # long time to get params.

        #result = self._update_params()

        result = self._do_cmd_resp(InstrumentCmds.GET_SYSTEM_CONFIGURATION, *args, **kwargs)
        return (next_state, (next_agent_state, result))

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
        prompt = self._wakeup(timeout=TIMEOUT)

        self._sync_clock(Parameter.TIME, Prompt.COMMAND, timeout, time_format="%Y/%m/%d, %H:%M:%S")

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
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.SEND_LAST_SAMPLE, *args, **kwargs)

        return (next_state, result)
        #return (next_state, (next_agent_state, result))

    def _handler_command_start_direct(self, *args, **kwargs):
        """
        """
        next_state = None
        result = None

        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        log.debug("_handler_command_start_direct: entering DA mode")
        return (next_state, (next_agent_state, result))

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        log.debug("IN _handler_direct_access_enter")

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        log.debug("%%% IN _handler_direct_access_exit")
        pass

    def _handler_direct_access_execute_direct(self, data):
        """
        """
        log.debug("IN _handler_direct_access_execute_direct")
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
        log.debug("in _build_set_command")
        my_state = self._protocol_fsm.get_current_state()
        log.debug("current_state = %s", my_state)
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
        log.debug("in _parse_set_response")
        my_state = self._protocol_fsm.get_current_state()
        log.debug("current_state = %s", my_state)

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
        my_state = self._protocol_fsm.get_current_state()
        log.debug("current_state = %s", my_state)

        self._promptbuf = ""
        self._linebuf = ""
        time.sleep(0.1)

        kwargs['expected_prompt'] = Prompt.COMMAND
        try:
            self.get_param = param
            get_cmd = param + '?' + NEWLINE
            log.debug("IN _build_get_command CMD = '%s'", get_cmd)
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return get_cmd

    def _parse_get_response(self, response, prompt):
        log.debug("in _parse_get_response RESPONSE+prompt = %s", str(response) + str(prompt) )
        my_state = self._protocol_fsm.get_current_state()
        log.debug("current_state = %s", my_state)
        if prompt == Prompt.ERR:
            raise InstrumentProtocolException('Protocol._parse_set_response : Set command not recognized: %s' % response)

        self._param_dict.update(response)
        for line in response.split(NEWLINE):
            log.debug("Scanning line through param_dict -> %s", line)
            self._param_dict.update(line)
            if not "?" in line and ">" != line:
                response2 = line

        if self.get_param not in response:
            self._promptbuf = ""
            self._linebuf = ""
            foo = self._get_raw_response(30, Prompt.COMMAND)
            log.debug("FOO = " + str(foo))
            foo = self._get_raw_response(30, Prompt.COMMAND)
            log.debug("FOO = " + str(foo))
            raise InstrumentParameterException('Failed to get a response for lookup of ' + self.get_param)

        self.get_count = 0
        return response2


