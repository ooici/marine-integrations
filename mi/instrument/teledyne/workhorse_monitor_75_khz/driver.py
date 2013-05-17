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


from mi.instrument.teledyne.driver import TeledyneInstrumentDriver
from mi.instrument.teledyne.driver import TeledyneProtocol
import base64

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
from mi.core.exceptions import InstrumentParameterExpirationException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import SampleException
from mi.core.instrument.driver_dict import DriverDictKey
# TODO: bring this code back in before delivery.
from mi.instrument.teledyne.workhorse_monitor_75_khz.particles import *

from mi.core.util import dict_equal

import socket


# default timeout.
TIMEOUT = 30


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
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
    GET_CALIBRATION = ProtocolEvent.GET_CALIBRATION
    GET_CONFIGURATION = ProtocolEvent.GET_CONFIGURATION
    SAVE_SETUP_TO_RAM = ProtocolEvent.SAVE_SETUP_TO_RAM
    SEND_LAST_SAMPLE = ProtocolEvent.SEND_LAST_SAMPLE
    GET_ERROR_STATUS_WORD = ProtocolEvent.GET_ERROR_STATUS_WORD
    CLEAR_ERROR_STATUS_WORD = ProtocolEvent.CLEAR_ERROR_STATUS_WORD
    GET_FAULT_LOG = ProtocolEvent.GET_FAULT_LOG
    CLEAR_FAULT_LOG = ProtocolEvent.CLEAR_FAULT_LOG
    GET_INSTRUMENT_TRANSFORM_MATRIX = ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX
    RUN_TEST_200 = ProtocolEvent.RUN_TEST_200

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


class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """
    COMMAND = '\r\n>\r\n>'
    ERR = 'ERR:'


class ScheduledJob(BaseEnum):
    """
    Complete this last.
    """
    CLOCK_SYNC = 'clock_sync'
    GET_CONFIGURATION = 'acquire_configuration'
    GET_CALIBRATION = 'acquire_calibration'
###############################################################################
# Driver
###############################################################################

class WorkhorseInstrumentDriver(TeledyneInstrumentDriver):
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
        TeledyneInstrumentDriver.__init__(self, evt_callback)

    '''
    TODO: create bug to remove this from template if does not cause issues
    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################

    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()
    '''
    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = WorkhorseProtocol(Prompt, NEWLINE, self._driver_event)
        log.debug("self._protocol = " + repr(self._protocol))
###########################################################################
# Protocol
###########################################################################

class WorkhorseProtocol(TeledyneProtocol):
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

        log.debug("IN WorkhorseProtocol.__init__")
        # Construct protocol superclass.
        TeledyneProtocol.__init__(self, prompts, newline, driver_event)

        # Build ADCPT protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)
        log.debug("ASSIGNED self._protocol_fsm")
        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)

        #self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.DISCOVER, self._handler_unknown_discover)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_command_clock_sync)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_CALIBRATION, self._handler_command_get_calibration)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET_CONFIGURATION, self._handler_command_get_configuration)

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
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET, self._handler_command_get)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_autosample_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET_CALIBRATION, self._handler_autosample_get_calibration)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET_CONFIGURATION, self._handler_autosample_get_configuration)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Build dictionaries for driver schema
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        # Add build handlers for device commands.
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
        self._add_response_handler(InstrumentCmds.OUTPUT_CALIBRATION_DATA, self._parse_output_calibration_data_response)
        self._add_response_handler(InstrumentCmds.SEND_LAST_SAMPLE, self._parse_send_last_sample_response)
        self._add_response_handler(InstrumentCmds.SAVE_SETUP_TO_RAM, self._parse_save_setup_to_ram_response)
        self._add_response_handler(InstrumentCmds.CLEAR_ERROR_STATUS_WORD, self._parse_clear_error_status_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_ERROR_STATUS_WORD, self._parse_error_status_response)
        self._add_response_handler(InstrumentCmds.CLEAR_FAULT_LOG, self._parse_clear_fault_log_response)
        self._add_response_handler(InstrumentCmds.GET_FAULT_LOG, self._parse_fault_log_response)
        self._add_response_handler(InstrumentCmds.GET_SYSTEM_CONFIGURATION, self._parse_get_system_configuration)

        self._add_response_handler(InstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX, self._parse_instrument_transform_matrix_response)
        self._add_response_handler(InstrumentCmds.RUN_TEST_200, self._parse_test_response)
        self._add_response_handler(InstrumentCmds.SET, self._parse_set_response)
        self._add_response_handler(InstrumentCmds.GET, self._parse_get_response)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be
        # filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(WorkhorseProtocol.sieve_function)

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

    @staticmethod
    def sieve_function(raw_data):
        """
        Chunker sieve method to help the chunker identify chunks.
        @returns a list of chunks identified, if any.
        The chunks are all the same type.
        """

        sieve_matchers = [ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER,
                          ADCP_COMPASS_CALIBRATION_REGEX_MATCHER,
                          ADCP_PD0_PARSED_REGEX_MATCHER]

        return_list = []

        for matcher in sieve_matchers:
            if matcher == ADCP_PD0_PARSED_REGEX_MATCHER:
                #
                # Have to cope with variable length binary records...
                # lets grab the length, then write a proper query to
                # snag it.
                #
                matcher2 = re.compile(r'\x7f\x7f(..)', re.DOTALL)
                for match in matcher2.finditer(raw_data):
                    l = unpack("H", match.group(1))
                    outer_pos = match.start()
                    ADCP_PD0_PARSED_TRUE_MATCHER = re.compile(r'\x7f\x7f(.{' + str(l[0]) + '})', re.DOTALL)
                    for match in ADCP_PD0_PARSED_TRUE_MATCHER.finditer(raw_data, outer_pos):
                        inner_pos = match.start()

                        if (outer_pos == inner_pos):
                            return_list.append((match.start(), match.end()))
            else:
                for match in matcher.finditer(raw_data):
                    return_list.append((match.start(), match.end()))

        return return_list

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        
                self.cmd_dict.add("cmd1",
                          timeout=60,
                          display_name="Command 1",
                          description="Execute a foo on the instrument",
                          return_type="bool",
                          return_units="Success",
                          return_description="Success (true) or failure (false)",
                          arguments=[CommandArgument(
                                     name="coeff",
                                     required=True,
                                     display_name="coefficient",
                                     description="The coefficient to use for calculation",
                                     type=CommandDictType.FLOAT,
                                     value_description="Should be between 1.97 and 2.34"
                                     ),
                                     CommandArgument(
                                     name="delay",
                                     required=False,
                                     display_name="delay time",
                                     description="The delay time to wait before executing",
                                     type=CommandDictType.FLOAT,
                                     units="seconds",
                                     value_description="Should be between 1.0 and 3.3 in increments of 0.1"
                                     )
                                    ]
                         )

        """

        self._cmd_dict.add(Capability.START_AUTOSAMPLE,
                           timeout=300,
                           display_name="start autosample",
                           description="Place the instrument into autosample mode")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE,
                           display_name="stop autosample",
                           description="Exit autosample mode and return to command mode")
        self._cmd_dict.add(Capability.CLOCK_SYNC,
                           display_name="sync clock")
        self._cmd_dict.add(Capability.GET_CALIBRATION,
                           display_name="get calibration")
        self._cmd_dict.add(Capability.GET_CONFIGURATION,
                           timeout=300,
                           display_name="get configuration")
        self._cmd_dict.add(Capability.GET_INSTRUMENT_TRANSFORM_MATRIX,
                           display_name="get instrument transform matrix")
        self._cmd_dict.add(Capability.SAVE_SETUP_TO_RAM,
                           display_name="save setup to ram")
        self._cmd_dict.add(Capability.SEND_LAST_SAMPLE,
                           display_name="send last sample")
        self._cmd_dict.add(Capability.GET_ERROR_STATUS_WORD,
                           display_name="get error status word")
        self._cmd_dict.add(Capability.CLEAR_ERROR_STATUS_WORD,
                           display_name="clear error status word")
        self._cmd_dict.add(Capability.GET_FAULT_LOG,
                           display_name="get fault log")
        self._cmd_dict.add(Capability.CLEAR_FAULT_LOG,
                           display_name="clear fault log")
        self._cmd_dict.add(Capability.RUN_TEST_200,
                           display_name="run test 200")


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
        @throws: InstrumentProtocolException if not in command or streaming
        """
        # Let's give it a try in unknown state
        log.debug("in apply_startup_params")
        if (self.get_current_state() != ProtocolState.COMMAND and
            self.get_current_state() != ProtocolState.AUTOSAMPLE):
            raise InstrumentProtocolException("Not in command or autosample state. Unable to apply startup params")

        logging = self._is_logging()
        # If we are in streaming mode and our configuration on the
        # instrument matches what we think it should be then we
        # don't need to do anything.

        if(not self._instrument_config_dirty()):
            log.debug("in apply_startup_params returning True")
            return True

        error = None

        try:
            if logging:
                # Switch to command mode,
                self._stop_logging()

            self._apply_params()

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            log.error("EXCEPTION WAS " + str(e))
            error = e

        finally:
            # Switch back to streaming
            if logging:
                my_state = self._protocol_fsm.get_current_state()
                log.debug("current_state = %s", my_state)
                self._start_logging()

        if(error):
            raise error

    def _instrument_config_dirty(self):
        """
        Read the startup config and compare that to what the instrument
        is configured too.  If they differ then return True
        @return: True if the startup config doesn't match the instrument
        @throws: InstrumentParameterException
        """
        # Refresh the param dict cache
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
    def _send_break_cmd(self):
        """
        Send a BREAK to attempt to wake the device.
        """
        log.debug("HOW DID I GET HERE......")

    def _send_break(self):
        """
        Send a BREAK to attempt to wake the device.
        """
        #self._connection.send_break(400)
        log.debug("IN _send_break, clearing buffer.")
        self._promptbuf = ''
        self._linebuf = ''
        self._send_break_cmd()
        break_confirmation = []
        log.debug("self._linebuf = " + self._linebuf)

        break_confirmation.append("[BREAK Wakeup A]" + NEWLINE + \
        "WorkHorse Broadband ADCP Version 50.40" + NEWLINE + \
        "Teledyne RD Instruments (c) 1996-2010" + NEWLINE + \
        "All Rights Reserved.")
        break_confirmation.append("[BREAK Wakeup A]")
        found = False
        timeout = 30 
        count = 0
        while (not found):
            log.debug("WAIT FOR BREAK TRY #" + str(count))
            count += 1
            for break_message in break_confirmation:
                if break_message in self._linebuf:
                    log.debug("GOT A BREAK MATCH ==> " + str(break_message))
                    found = True
            if count > timeout:
                if True != found:
                    raise InstrumentTimeoutException("NO BREAK RESPONSE.")
            time.sleep(1)
        self._chunker._clean_buffer(len(self._chunker.raw_chunk_list))
        self._promptbuf = ''
        self._linebuf = ''
        return True

    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the device.
        """
        log.debug("IN _send_wakeup")

        self._connection.send(NEWLINE)
        log.debug("SENT A NEWLINE")

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. 
        """
        error = None
        logging = self._is_logging()

        try:
            if logging:
                # Switch to command mode,
                self._stop_logging()

            # UPDATE CODE HERE
            # Get old param dict config.
            old_config = self._param_dict.get_config()

            kwargs['expected_prompt'] = Prompt.COMMAND

            cmds = dir(Parameter)
            results = ""
            for attr in sorted(cmds):
                if attr not in ['dict', 'has', 'list', 'ALL']:
                    if not attr.startswith("_"):
                        key = getattr(Parameter, attr)
                        result = self._do_cmd_resp(InstrumentCmds.GET, key, **kwargs)
                        results += result + NEWLINE

            result = self._do_cmd_resp(InstrumentCmds.GET, key, **kwargs)
            new_config = self._param_dict.get_config()

            if not dict_equal(new_config, old_config):
                self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

            # UPDATE CODE HERE

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            log.error("EXCEPTION WAS " + str(e))
            error = e

        finally:
            # Switch back to streaming
            if logging:
                my_state = self._protocol_fsm.get_current_state()
                log.debug("current_state = %s", my_state)
                self._start_logging()

        if(error):
            raise error

        return results

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.
        Pass it to extract_sample with the appropriate particle
        objects and REGEXes.
        """

        if (self._extract_sample(ADCP_COMPASS_CALIBRATION_DataParticle,
                                 ADCP_COMPASS_CALIBRATION_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("_got_chunk - successful match for ADCP_COMPASS_CALIBRATION_DataParticle")

        if (self._extract_sample(ADCP_PD0_PARSED_DataParticle,
                                 ADCP_PD0_PARSED_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("_got_chunk - successful match for ADCP_PD0_PARSED_DataParticle")

        if (self._extract_sample(ADCP_SYSTEM_CONFIGURATION_DataParticle,
                                 ADCP_SYSTEM_CONFIGURATION_REGEX_MATCHER,
                                 chunk,
                                 timestamp)):
            log.debug("_got_chunk - successful match for ADCP_SYSTEM_CONFIGURATION_DataParticle")

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

    def _parse_output_calibration_data_response(self, response, prompt):
        """
        Return the output from the calibration request base 64 encoded
        """
        return base64.b64encode(response)

    def _parse_get_system_configuration(self, response, prompt):
        """
        return the output from the get system configuration request base 64 encoded
        """
        return base64.b64encode(response)

    def _parse_send_last_sample_response(self, response, prompt):
        """
        get the response from the CE command.
        Remove the >\n> from the end of it.
        return it base64 encoded
        """

        response = re.sub("CE\r\n", "", response)
        log.debug("response = " + str(response))
        return (True, base64.b64encode(response))

    def _parse_save_setup_to_ram_response(self, response, prompt):
        """
        save settings to nv ram. return response.
        """

        # Cleanup the results
        response = re.sub("CK\r\n", "", response)
        response = re.sub("\[", "", response)
        response = re.sub("\]", "", response)
        response = re.sub("\r\n>", "", response)
        return (True, response)

    def _parse_clear_error_status_response(self, response, prompt):
        """
        Remove the sent command from the response and return it
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
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.RUN_TEST_200, *args, **kwargs)

        return (next_state, result)

    def _handler_command_get_instrument_transform_matrix(self, *args, **kwargs):
        """
        save setup to ram.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX, *args, **kwargs)

        return (next_state, result)

    def _handler_command_save_setup_to_ram(self, *args, **kwargs):
        """
        save setup to ram.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.SAVE_SETUP_TO_RAM, *args, **kwargs)

        return (next_state, result)

    def _handler_command_clear_error_status_word(self, *args, **kwargs):
        """
        clear the error status word
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.CLEAR_ERROR_STATUS_WORD, *args, **kwargs)
        return (next_state, result)

    def _handler_command_acquire_error_status_word(self, *args, **kwargs):
        """
        read the error status word
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.DISPLAY_ERROR_STATUS_WORD, *args, **kwargs)
        return (next_state, result)

    def _handler_command_display_fault_log(self, *args, **kwargs):
        """
        display the error log.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = Prompt.COMMAND
        result = self._do_cmd_resp(InstrumentCmds.GET_FAULT_LOG, *args, **kwargs)
        return (next_state, result)

    def _handler_command_clear_fault_log(self, *args, **kwargs):
        """
        clear the error log.
        """
        next_state = None
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
        Enter unknown state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        pass

    ######################################################
    #                                                    #
    ######################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result), (ProtocolState.COMMAND or
        State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """
        log.debug("in _handler_unknown_discover")
        next_state = None
        next_agent_state = None

        logging = self._is_logging()

        if(logging == None):
            raise InstrumentProtocolException('_handler_unknown_discover - unable to to determine state')

        elif(logging):
            next_state = ProtocolState.AUTOSAMPLE
            next_agent_state = ResourceAgentState.STREAMING

        else:
            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.IDLE
        return (next_state, next_agent_state)

    ######################################################
    #                                                    #
    ######################################################

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
        log.debug("IN _handler_autosample_exit")

        pass

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        result = None
        kwargs['expected_prompt'] = Prompt.COMMAND
        kwargs['timeout'] = 30

        log.info("SYNCING TIME WITH SENSOR.")
        resp = self._do_cmd_resp(InstrumentCmds.SET, Parameter.TIME, get_timestamp_delayed("%Y/%m/%d, %H:%M:%S"), **kwargs)
        log.debug("SET TIME RESPONSE = " + str(resp))

        # Save setup to nvram and switch to autosample if successful.
        resp = self._do_cmd_resp(InstrumentCmds.SAVE_SETUP_TO_RAM, *args, **kwargs)
        log.debug("SAVE_SETUP_TO_RAM RESPONSE = " + str(resp))

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

        self._stop_logging(timeout)

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    def _handler_command_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @throws InstrumentParameterException if missing or invalid parameter.
        """

        next_state = None
        result = None
        error = None

        # Grab a baseline time for calculating expiration time.  It is assumed
        # that all data if valid if acquired after this time.
        expire_time = self._param_dict.get_current_timestamp()

        # build a list of parameters we need to get
        param_list = self._get_param_list(*args, **kwargs)

        try:
            # Take a first pass at getting parameters.  If they are
            # expired an exception will be raised.
            result = self._get_param_result(param_list, expire_time)
        except InstrumentParameterExpirationException as e:
            # In the second pass we need to update parameters, it is assumed
            # that _update_params does everything required to refresh all
            # parameters or at least those that would expire.

            log.debug("in _handler_command_get Parameter expired, refreshing, %s", e)

            if self._is_logging():
                log.debug("I am logging")
                try:
                    # Switch to command mode,
                    self._stop_logging(*args, **kwargs)

                    self._update_params()
                    # Take a second pass at getting values, this time is should
                    # have all fresh values.
                    log.debug("Fetching parameters for the second time")
                    result = self._get_param_result(param_list, expire_time)
                # Catch all error so we can put ourself back into
                # streaming.  Then rethrow the error
                except Exception as e:
                    error = e

                finally:
                    # Switch back to streaming
                    self._start_logging()

                if(error):
                    raise error
            else:
                log.debug("I am not logging")
                self._update_params()
                # Take a second pass at getting values, this time is should
                # have all fresh values.
                log.debug("Fetching parameters for the second time")
                result = self._get_param_result(param_list, expire_time)
            '''
            TODO: Just commented the below out. i think it
            was accidentally left in. if all works, then it should be perm removed.

            # Take a second pass at getting values, this time is should
            # have all fresh values.
            log.debug("Fetching parameters for the second time")
            result = self._get_param_result(param_list, expire_time)
            '''
        return (next_state, result)

    def _handler_autosample_get_calibration(self, *args, **kwargs):
        """
        execute a get calibration from autosample mode.  
        For this command we have to move the instrument
        into command mode, get calibration, then switch back.  If an
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
            self._stop_logging(*args, **kwargs)

            kwargs['timeout'] = 120
            result = self._do_cmd_resp(InstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging()

        if(error):
            raise error
        result = base64.b64decode(result)
        return (next_state, (next_agent_state, self._sanitize(result)))

    def _handler_autosample_get_configuration(self, *args, **kwargs):
        """
        execute a get configuration from autosample mode.  
        For this command we have to move the instrument
        into command mode, get configuration, then switch back.  If an
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
            self._stop_logging(*args, **kwargs)

            # Sync the clock
            timeout = kwargs.get('timeout', TIMEOUT)
            result = self._do_cmd_resp(InstrumentCmds.GET_SYSTEM_CONFIGURATION, *args, **kwargs)

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging()

        if(error):
            raise error
        
        result = base64.b64decode(result)
        return (next_state, (next_agent_state, result))

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
        log.debug("in _handler_autosample_clock_sync")
        try:
            # Switch to command mode,
            self._stop_logging(*args, **kwargs)

            # Sync the clock
            timeout = kwargs.get('timeout', TIMEOUT)

            self._sync_clock(InstrumentCmds.SET, Parameter.TIME, timeout, time_format="%Y/%m/%d,%H:%M:%S")

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
        log.debug("IN _handler_command_set")
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
            result = self._set_params(params, startup)

        return (next_state, result)

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
        result = None
        startup = False
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        try:
            startup = args[1]
        except IndexError:
            pass

        log.debug("calling _verify_not_readonly ARGS = " + repr(args))
        self._verify_not_readonly(*args, **kwargs)

        for (key, val) in params.iteritems():
            result = self._do_cmd_resp(InstrumentCmds.SET, key, val, **kwargs)
        self._update_params()
        return result

    def _sanitize(self, s):
        s = s.replace('\xb3', '_')
        s = s.replace('\xbf', '_')
        s = s.replace('\xc0', '_')
        s = s.replace('\xd9', '_')
        s = s.replace('\xda', '_')
        s = s.replace('\xf8', '_')

        return s

    def _handler_command_get_calibration(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        log.debug("IN _handler_command_get_calibration")
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 120

        result = self._do_cmd_resp(InstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)
        result = base64.b64decode(result)
        return (next_state, (next_agent_state, self._sanitize(result)))

    def _handler_command_get_configuration(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 120  # long time to get params.

        result = self._do_cmd_resp(InstrumentCmds.GET_SYSTEM_CONFIGURATION, *args, **kwargs)
        result = self._sanitize(base64.b64decode(result))
        log.debug("RESULT gc = " + str(result))
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

        self._sync_clock(InstrumentCmds.SET, Parameter.TIME, timeout, time_format="%Y/%m/%d,%H:%M:%S")

        return (next_state, (next_agent_state, result))

    def _handler_command_send_last_sample(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        log.debug("***********IN _handler_command_send_last_sample")
        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = '>\r\n>' # special one off prompt.
        (result, last_sample) = self._do_cmd_resp(InstrumentCmds.SEND_LAST_SAMPLE, *args, **kwargs)

        decoded_last_sample = base64.b64decode(last_sample)
        return (next_state, (next_agent_state, decoded_last_sample))

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
            raise InstrumentParameterException('Protocol._parse_set_response : Set command not recognized: %s' % response)

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

        kwargs['expected_prompt'] = Prompt.COMMAND + NEWLINE + Prompt.COMMAND
        try:
            self.get_param = param
            get_cmd = param + '?' + NEWLINE
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return get_cmd

    def _parse_get_response(self, response, prompt):
        log.debug("GET RESPONSE = " + repr(response))
        if prompt == Prompt.ERR:
            raise InstrumentProtocolException('Protocol._parse_set_response : Set command not recognized: %s' % response)

        while (not response.endswith('\r\n>\r\n>')) or ('?' not in response):
            (prompt, response) = self._get_raw_response(30, Prompt.COMMAND)
            time.sleep(1)

        self._param_dict.update(response)

        for line in response.split(NEWLINE):
            self._param_dict.update(line)
            if not "?" in line and ">" != line:
                response = line

        if self.get_param not in response:
            raise InstrumentParameterException('Failed to get a response for lookup of ' + self.get_param)

        self.get_count = 0
        return response

    def _wakeup(self, timeout, delay=1):
        """
        Clear buffers and send a wakeup command to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        # Clear the prompt buffer.
        #log.debug("clearing promptbuf: %s" % self._promptbuf)
        self._promptbuf = ''

        # Grab time for timeout.
        starttime = time.time()

        # Send a line return and wait a sec.
        log.trace('Sending wakeup. timeout=%s' % timeout)
        self._send_wakeup()
        time.sleep(delay)

        #log.debug("Prompts: %s" % self._get_prompts())

        for item in self._get_prompts():
            #log.debug("buffer: %s" % self._promptbuf)
            #log.debug("find prompt: %s" % item)
            index = self._promptbuf.find(item)
            #log.debug("Got prompt (index: %s): %s " % (index, repr(self._promptbuf)))
            if index >= 0:
                log.trace('wakeup got prompt: %s' % repr(item))
                return item

        return None

    def _is_logging(self, timeout=TIMEOUT):
        """
        Poll the instrument to see if we are in logging mode.  Return True
        if we are, False if not.
        @param: timeout - Command timeout
        @return: True - instrument logging, False - not logging
        """
        log.debug("in _is_logging")

        self._linebuf = ""
        self._promptbuf = ""

        prompt = self._wakeup(timeout=TIMEOUT)
        log.debug("********** GOT PROMPT" + repr(prompt))
        if Prompt.COMMAND == prompt:
            logging = False
            log.debug("COMMAND MODE!")
        else:
            logging = True
            log.debug("AUTOSAMPLE MODE!")

        return logging

    def _start_logging(self, timeout=TIMEOUT):
        """
        Command the instrument to start logging
        @param timeout: how long to wait for a prompt
        @return: True if successful
        @throws: InstrumentProtocolException if failed to start logging
        """
        log.debug("in _start_logging - Start Logging!")
        if(self._is_logging()):
            return True
        self._do_cmd_no_resp(InstrumentCmds.START_DEPLOYMENT, timeout=timeout)
        time.sleep(1)

        return True

    def _stop_logging(self, timeout=TIMEOUT):
        """
        Command the instrument to stop logging
        @param timeout: how long to wait for a prompt
        @return: True if successful
        @throws: InstrumentTimeoutException if prompt isn't seen
        @throws: InstrumentProtocolException failed to stop logging
        """
        log.debug("in Stop Logging!")
        # Issue the stop command.


        self._send_break()

        # Prompt device until command prompt is seen.
        self._wakeup_until(timeout, Prompt.COMMAND)

        # set logging to false, as we just got a prompt after a break
        logging = False

        if self._is_logging(timeout):
            raise InstrumentProtocolException("failed to stop logging")

        return True

