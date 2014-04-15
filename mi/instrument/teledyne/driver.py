"""
@package mi.instrument.teledyne.driver
@file marine-integrations/mi/instrument/teledyne/driver.py
@author Roger Unwin
@brief Driver for the teledyne family
Release notes:
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import time
import datetime as dt
from mi.core.common import BaseEnum
from mi.core.time import get_timestamp_delayed

from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterExpirationException

from mi.core.log import get_logger; log = get_logger()

from mi.core.instrument.instrument_fsm import InstrumentFSM

from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol

from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState

from mi.core.instrument.driver_dict import DriverDictKey

from mi.core.util import dict_equal

import re
import base64

# default timeout.
TIMEOUT = 20

# newline.
NEWLINE = '\r\n'

# TODO: do i keep below two defines for _do_cmd_resp
DEFAULT_CMD_TIMEOUT=20
DEFAULT_WRITE_DELAY=0

class TeledynePrompt(BaseEnum):
    """
    Device i/o prompts..
    """
    COMMAND = '\r\n>\r\n>'
    ERR = 'ERR:'
    # POWERING DOWN MESSAGE
    # "Powering Down"

class TeledyneParameter(DriverParameter):
    """
    Device parameters
    """
    #
    # set-able parameters
    #
    SERIAL_DATA_OUT = 'CD'              # 000 000 000 Serial Data Out (Vel;Cor;Amp PG;St;P0 P1;P2;P3)
    INSTRUMENT_ID = 'CI'                # Int 0-255
    XMIT_POWER = 'CQ'                   # 0=Low, 255=High
    SPEED_OF_SOUND = 'EC'               # 1500  Speed Of Sound (m/s)
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

    #
    # Workhorse parameters
    #
    SERIAL_FLOW_CONTROL = 'CF'
    BANNER = 'CH'
    SLEEP_ENABLE = 'CL'
    SAVE_NVRAM_TO_RECORDER = 'CN'
    POLLED_MODE = 'CP'
    PITCH = 'EP'
    ROLL = 'ER'

    LATENCY_TRIGGER = 'CX'
    HEADING_ALIGNMENT = 'EA'
    DATA_STREAM_SELECTION ='PD'
    ENSEMBLE_PER_BURST ='TC'
    BUFFERED_OUTPUT_PERIOD ='TX'
    SAMPLE_AMBIENT_SOUND ='WQ'
    TRANSDUCER_DEPTH ='ED'



class TeledyneInstrumentCmds(BaseEnum):
    """
    Device specific commands
    Represents the commands the driver implements and the string that
    must be sent to the instrument to execute the command.
    """

    OUTPUT_CALIBRATION_DATA = 'AC'
    BREAK = 'break' # < case sensitive!!!!
    SEND_LAST_SAMPLE = 'CE'
    SAVE_SETUP_TO_RAM = 'CK'
    FACTORY_SETS = 'CR1' #Factory default set
    USER_SETS = 'CR0'  #User default set
    START_LOGGING = 'CS'
    CLEAR_ERROR_STATUS_WORD = 'CY0'         # May combine with next
    DISPLAY_ERROR_STATUS_WORD = 'CY1'       # May combine with prior
    CLEAR_FAULT_LOG = 'FC'
    GET_FAULT_LOG = 'FD'

    GET_SYSTEM_CONFIGURATION = 'PS0'
    GET_INSTRUMENT_TRANSFORM_MATRIX = 'PS3'
    RUN_TEST_200 = 'PT200'
    SET = ' '  # leading spaces are OK. set is just PARAM_NAME next to VALUE
    GET = '  '



class TeledyneProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS

class TeledyneProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    INIT_PARAMS = DriverEvent.INIT_PARAMS
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

    FACTORY_SETS = "FACTORY_DEFAULT_SETTINGS"
    USER_SETS = "USER_DEFAULT_SETTINGS"
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
    RECOVER_AUTOSAMPLE = 'PROTOCOL_EVENT_RECOVER_AUTOSAMPLE'
    RESTORE_FACTORY_PARAMS = "PROTOCOL_EVENT_RESTORE_FACTORY_PARAMS"
    #POWER_DOWN = "PROTOCOL_EVENT_POWER_DOWN"


class TeledyneCapability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = TeledyneProtocolEvent.CLOCK_SYNC
    GET_CALIBRATION = TeledyneProtocolEvent.GET_CALIBRATION
    GET_CONFIGURATION = TeledyneProtocolEvent.GET_CONFIGURATION
    SAVE_SETUP_TO_RAM = TeledyneProtocolEvent.SAVE_SETUP_TO_RAM
    SEND_LAST_SAMPLE = TeledyneProtocolEvent.SEND_LAST_SAMPLE
    GET_ERROR_STATUS_WORD = TeledyneProtocolEvent.GET_ERROR_STATUS_WORD
    CLEAR_ERROR_STATUS_WORD = TeledyneProtocolEvent.CLEAR_ERROR_STATUS_WORD
    GET_FAULT_LOG = TeledyneProtocolEvent.GET_FAULT_LOG
    CLEAR_FAULT_LOG = TeledyneProtocolEvent.CLEAR_FAULT_LOG
    GET_INSTRUMENT_TRANSFORM_MATRIX = TeledyneProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX
    RUN_TEST_200 = TeledyneProtocolEvent.RUN_TEST_200
    FACTORY_SETS = TeledyneProtocolEvent.FACTORY_SETS
    USER_SETS = TeledyneProtocolEvent.USER_SETS

class TeledyneScheduledJob(BaseEnum):

    CLOCK_SYNC = 'clock_sync'
    GET_CONFIGURATION = 'acquire_configuration'
    GET_CALIBRATION = 'acquire_calibration'

class TeledyneInstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver Family SubClass
    """
    def __init__(self, evt_callback):
        """
        Driver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED,
            DriverEvent.DISCOVER,
            self._handler_connected_discover)

    def _handler_connected_discover(self, event, *args, **kwargs):
        # Redefine discover handler so that we can apply startup params
        # when we discover. Gotta get into command mode first though.
        log.trace("in TeledyneInstrumentDriver._handler_connected_discover calling SingleConnectionInstrumentDriver._handler_connected_protocol_event")
        result = SingleConnectionInstrumentDriver._handler_connected_protocol_event(self, event, *args, **kwargs)
        log.trace("in TeledyneInstrumentDriver._handler_connected_discover apply_startup_params")
        self.apply_startup_params()
        return result

class TeledyneProtocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol Family SubClass
    """
    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """

        self.last_wakeup = 0

        # Construct protocol superclass.
        log.trace("IN TeledyneProtocol.__init__")
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        self.last_wakeup = 0

        # Build ADCPT protocol state machine.
        self._protocol_fsm = InstrumentFSM(TeledyneProtocolState, TeledyneProtocolEvent,
                            TeledyneProtocolEvent.ENTER, TeledyneProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(TeledyneProtocolState.UNKNOWN, TeledyneProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(TeledyneProtocolState.UNKNOWN, TeledyneProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(TeledyneProtocolState.UNKNOWN, TeledyneProtocolEvent.DISCOVER, self._handler_unknown_discover)

        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.EXIT, self._handler_command_exit)

        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.INIT_PARAMS, self._handler_command_init_params)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_command_clock_sync)

        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.GET_CALIBRATION, self._handler_command_get_calibration)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.GET_CONFIGURATION, self._handler_command_get_configuration)

        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.SAVE_SETUP_TO_RAM, self._handler_command_save_setup_to_ram)

        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.SEND_LAST_SAMPLE, self._handler_command_send_last_sample)

        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, self._handler_command_get_instrument_transform_matrix)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.RUN_TEST_200, self._handler_command_run_test_200)
        #//
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.FACTORY_SETS, self._handler_command_factory_sets)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.USER_SETS, self._handler_command_user_sets)
        #//
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.GET_ERROR_STATUS_WORD, self._handler_command_acquire_error_status_word)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.CLEAR_ERROR_STATUS_WORD, self._handler_command_clear_error_status_word)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.CLEAR_FAULT_LOG, self._handler_command_clear_fault_log)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.GET_FAULT_LOG, self._handler_command_display_fault_log)

        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.INIT_PARAMS, self._handler_autosample_init_params)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.GET, self._handler_command_get)

        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.SCHEDULED_CLOCK_SYNC, self._handler_autosample_clock_sync)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.GET_CALIBRATION, self._handler_autosample_get_calibration)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.GET_CONFIGURATION, self._handler_autosample_get_configuration)

        # we may have got a particle and slipped into AUTOSAMPLE, so we should honor discover...
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.DISCOVER, self._handler_unknown_discover) 

        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.RECOVER_AUTOSAMPLE, self._handler_recover_autosample)




        self._protocol_fsm.add_handler(TeledyneProtocolState.DIRECT_ACCESS, TeledyneProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(TeledyneProtocolState.DIRECT_ACCESS, TeledyneProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(TeledyneProtocolState.DIRECT_ACCESS, TeledyneProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(TeledyneProtocolState.DIRECT_ACCESS, TeledyneProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Build dictionaries for driver schema
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        # Add build handlers for device commands.
        self._add_build_handler(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.SEND_LAST_SAMPLE, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.SAVE_SETUP_TO_RAM, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.START_LOGGING, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.DISPLAY_ERROR_STATUS_WORD, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.CLEAR_ERROR_STATUS_WORD, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.CLEAR_FAULT_LOG, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.GET_FAULT_LOG, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.GET_SYSTEM_CONFIGURATION, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.RUN_TEST_200, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.FACTORY_SETS, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.USER_SETS, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.SET, self._build_set_command)
        self._add_build_handler(TeledyneInstrumentCmds.GET, self._build_get_command)
        #
        # Response handlers
        #
        #
        # Response handlers
        #
        self._add_response_handler(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, self._parse_output_calibration_data_response)
        self._add_response_handler(TeledyneInstrumentCmds.SEND_LAST_SAMPLE, self._parse_send_last_sample_response)
        self._add_response_handler(TeledyneInstrumentCmds.SAVE_SETUP_TO_RAM, self._parse_save_setup_to_ram_response)
        self._add_response_handler(TeledyneInstrumentCmds.CLEAR_ERROR_STATUS_WORD, self._parse_clear_error_status_response)
        self._add_response_handler(TeledyneInstrumentCmds.DISPLAY_ERROR_STATUS_WORD, self._parse_error_status_response)
        self._add_response_handler(TeledyneInstrumentCmds.CLEAR_FAULT_LOG, self._parse_clear_fault_log_response)
        self._add_response_handler(TeledyneInstrumentCmds.GET_FAULT_LOG, self._parse_fault_log_response)
        self._add_response_handler(TeledyneInstrumentCmds.GET_SYSTEM_CONFIGURATION, self._parse_get_system_configuration)

        self._add_response_handler(TeledyneInstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX, self._parse_instrument_transform_matrix_response)
        self._add_response_handler(TeledyneInstrumentCmds.RUN_TEST_200, self._parse_test_response)

        self._add_response_handler(TeledyneInstrumentCmds.FACTORY_SETS, self._parse_test_response)
        self._add_response_handler(TeledyneInstrumentCmds.USER_SETS, self._parse_test_response)

        self._add_response_handler(TeledyneInstrumentCmds.SET, self._parse_set_response)
        self._add_response_handler(TeledyneInstrumentCmds.GET, self._parse_get_response)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(TeledyneProtocolState.UNKNOWN)

        # commands sent sent to device to be
        # filtered in responses for telnet DA
        self._sent_cmds = []

        self._add_scheduler_event(TeledyneScheduledJob.GET_CONFIGURATION, TeledyneProtocolEvent.GET_CONFIGURATION)
        self._add_scheduler_event(TeledyneScheduledJob.GET_CALIBRATION, TeledyneProtocolEvent.GET_CALIBRATION)
        self._add_scheduler_event(TeledyneScheduledJob.CLOCK_SYNC, TeledyneProtocolEvent.SCHEDULED_CLOCK_SYNC)

        # Workaround for problem where send last sample makes the driver 
        # believe it is in autosample mode...
        self.disable_autosample_recover = False

    def _build_param_dict(self):
        pass

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _build_simple_command(self, cmd):
        """
        Build handler for basic adcpt commands.
        @param cmd the simple adcpt command to format
                (no value to attach to the command)
        @retval The command to be sent to the device.
        """
        log.trace("build_simple_command: %s" % cmd)
        return cmd + NEWLINE

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if TeledyneCapability.has(x)]

    def _sync_clock(self, command, date_time_param, timeout=TIMEOUT, delay=1, time_format="%d %b %Y %H:%M:%S"):
        """
        Send the command to the instrument to syncronize the clock
        @param date_time_param: date time parameter that we want to set
        @param prompts: expected prompt
        @param timeout: command timeout
        @param delay: wakeup delay
        @param time_format: time format string for set command
        @return: true if the command is successful
        @throws: InstrumentProtocolException if command fails
        """
        prompt = self._wakeup(timeout=3, delay=delay)

        # lets clear out any past data so it doesnt confuse the command
        self._linebuf = ''
        self._promptbuf = ''

        prompt = self._wakeup(timeout=3, delay=delay)
        str_val = get_timestamp_delayed(time_format)
        reply = self._do_cmd_direct(date_time_param + str_val)
        time.sleep(1)
        reply = self._get_response(TIMEOUT)

        return True

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

        @throws: InstrumentProtocolException if not in command or streaming
        """
        # Let's give it a try in unknown state
        log.debug("in apply_startup_params")
        if (self.get_current_state() != TeledyneProtocolState.COMMAND and
            self.get_current_state() != TeledyneProtocolState.AUTOSAMPLE):
            raise InstrumentProtocolException("Not in command or autosample state. Unable to apply startup params")

        logging = self._is_logging()
        # If we are in streaming mode and our configuration on the
        # instrument matches what we think it should be then we
        # don't need to do anything.

        if(not self._instrument_config_dirty()):
            log.trace("in apply_startup_params returning True")
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
                log.debug("GOING BACK INTO LOGGING")
                my_state = self._protocol_fsm.get_current_state()
                log.trace("current_state = %s", my_state)
                self._start_logging()

        if(error):
            raise error

    def _apply_params(self):
        """
        apply startup parameters to the instrument.
        @throws: InstrumentProtocolException if in wrong mode.
        """
        log.debug("IN _apply_params")
        config = self.get_startup_config()
        # Pass true to _set_params so we know these are startup values
        self._set_params(config, True)

    def _get_params(self):
        return dir(TeledyneParameter)

    def _getattr_key(self, attr):
        return getattr(TeledyneParameter, attr)

    def _has_parameter(self, param):
        return TeledyneParameter.has(param)

    # TODO: does this below over-ride work?

    def _do_cmd_resp(self, cmd, *args, **kwargs):
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
        # Get timeout and initialize response.
        timeout = kwargs.get('timeout', DEFAULT_CMD_TIMEOUT)
        expected_prompt = kwargs.get('expected_prompt', None)
        write_delay = kwargs.get('write_delay', DEFAULT_WRITE_DELAY)
        retval = None

        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            raise InstrumentProtocolException('Cannot build command: %s' % cmd)

        cmd_line = build_handler(cmd, *args)
        # Wakeup the device, pass up exception if timeout

        if (self.last_wakeup + 30) > time.time():
            self.last_wakeup = time.time()
        else:
            prompt = self._wakeup(timeout=3)
        # Clear line and prompt buffers for result.


        self._linebuf = ''
        self._promptbuf = ''

        # Send command.
        log.debug('_do_cmd_resp: %s' % repr(cmd_line))

        if (write_delay == 0):
            self._connection.send(cmd_line)
        else:
            for char in cmd_line:
                self._connection.send(char)
                time.sleep(write_delay)

        # Wait for the prompt, prepare result and return, timeout exception
        (prompt, result) = self._get_response(timeout,
                                              expected_prompt=expected_prompt)
        resp_handler = self._response_handlers.get((self.get_current_state(), cmd), None) or \
            self._response_handlers.get(cmd, None)
        resp_result = None
        if resp_handler:
            resp_result = resp_handler(result, prompt)

        return resp_result

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. 
        """
        log.debug("in _update_params")
        error = None
        logging = self._is_logging()

        try:
            if logging:
                # Switch to command mode,
                self._stop_logging()

            # Get old param dict config.
            old_config = self._param_dict.get_config()

            kwargs['expected_prompt'] = TeledynePrompt.COMMAND

            cmds = self._get_params()
            results = ""
            for attr in sorted(cmds):
                if attr not in ['dict', 'has', 'list', 'ALL']:
                    if not attr.startswith("_"):
                        key = self._getattr_key(attr)
                        result = self._do_cmd_resp(TeledyneInstrumentCmds.GET, key, **kwargs)
                        results += result + NEWLINE

            new_config = self._param_dict.get_config()

            if not dict_equal(new_config, old_config):
                self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            log.error("EXCEPTION WAS " + str(e))
            error = e

        finally:
            # Switch back to streaming
            if logging:
                log.debug("GOING BACK INTO LOGGING")
                my_state = self._protocol_fsm.get_current_state()
                log.debug("current_state = %s calling start_logging", my_state)
                self._start_logging()

        if(error):
            raise error

        return results

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        log.trace("in _set_params")
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
        log.trace("_set_params calling _verify_not_readonly ARGS = " + repr(args))
        self._verify_not_readonly(*args, **kwargs)
        for (key, val) in params.iteritems():
            result = self._do_cmd_resp(TeledyneInstrumentCmds.SET, key, val, **kwargs)
        log.trace("_set_params calling _update_params")
        self._update_params()
        return result

    def _get_param_result(self, param_list, expire_time):
        """
        return a dictionary of the parameters and values
        @param expire_time: baseline time for expiration calculation
        @return: dictionary of values
        @throws InstrumentParameterException if missing or invalid parameter
        @throws InstrumentParameterExpirationException if value is expired.
        """
        result = {}

        for param in param_list:
            val = self._param_dict.get(param, expire_time)
            result[param] = val

        return result

    def _send_break_cmd(self, duration=500):
        """
        Send a BREAK to attempt to wake the device.
        """
        log.error("SENDING BREAK TO PORT AGENT......")
        #self._connection.send_break(duration)

    def _send_break(self, duration=500):
        """
        Send a BREAK to attempt to wake the device.
        """
        log.debug("IN _send_break, clearing buffer.")
        self._promptbuf = ''
        self._linebuf = ''
        self._send_break_cmd(duration)
        break_confirmation = []
        log.trace("self._linebuf = " + self._linebuf)

        break_confirmation.append("[BREAK Wakeup A]" + NEWLINE + \
        "WorkHorse Broadband ADCP Version 50.40" + NEWLINE + \
        "Teledyne RD Instruments (c) 1996-2010" + NEWLINE + \
        "All Rights Reserved.")

        break_confirmation.append("[BREAK Wakeup A]")
        found = False
        timeout = 30
        count = 0
        while (not found):
            log.error("WAIT FOR BREAK TRY #" + str(count))
            log.error("ROGER self._linebuf = " + str(self._linebuf))
            count += 1
            for break_message in break_confirmation:
                if break_message in self._linebuf:
                    log.error("GOT A BREAK MATCH ==> " + str(break_message))
                    found = True
            if count > (timeout * 10):
                if True != found:
                    raise InstrumentTimeoutException("NO BREAK RESPONSE.")
            time.sleep(0.1)
        self._chunker._clean_buffer(len(self._chunker.raw_chunk_list))
        self._promptbuf = ''
        self._linebuf = ''
        log.trace("leaving send_break")
        return True

    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the device.
        """
        log.trace("IN _send_wakeup")

        self._connection.send(NEWLINE)

    def _wakeup(self, timeout=3, delay=1):
        """
        Clear buffers and send a wakeup command to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """

        self.last_wakeup = time.time()
        # Clear the prompt buffer.
        self._promptbuf = ''

        # Grab time for timeout.
        starttime = time.time()
        endtime = starttime + float(timeout)

        # Send a line return and wait a sec.
        log.debug('Sending wakeup. timeout=%s' % timeout)
        self._send_wakeup()

        while time.time() < endtime:
            time.sleep(0.05)
            for item in self._get_prompts():
                index = self._promptbuf.find(item)
                if index >= 0:
                    log.debug('wakeup got prompt: %s' % repr(item))
                    return item
        return None


    def _instrument_config_dirty(self):
        """
        Read the startup config and compare that to what the instrument
        is configured too.  If they differ then return True
        @return: True if the startup config doesn't match the instrument
        @throws: InstrumentParameterException
        """
        log.trace("in _instrument_config_dirty")
        # Refresh the param dict cache
        #self._update_params()

        startup_params = self._param_dict.get_startup_list()
        log.trace("Startup Parameters: %s" % startup_params)

        for param in startup_params:
            if not self._has_parameter(param):
                raise InstrumentParameterException("in _instrument_config_dirty")

            if (self._param_dict.get(param) != self._param_dict.get_config_value(param)):
                log.trace("DIRTY: %s %s != %s" % (param, self._param_dict.get(param), self._param_dict.get_config_value(param)))
                return True

        log.trace("Clean instrument config")
        return False

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

        prompt = self._wakeup(timeout=3)
        #log.debug("********** GOT PROMPT" + repr(prompt))
        if TeledynePrompt.COMMAND == prompt:
            logging = False
            log.trace("COMMAND MODE!")
        else:
            logging = True
            log.trace("AUTOSAMPLE MODE!")

        return logging

    def _start_logging(self, timeout=TIMEOUT):
        """
        Command the instrument to start logging
        @param timeout: how long to wait for a prompt
        @return: True if successful
        @throws: InstrumentProtocolException if failed to start logging
        """
        log.debug("in _start_logging - are we logging? ")
        if (self._is_logging()):
            log.debug("ALREADY LOGGING")
            return True
        log.debug("SENDING START LOGGING")
        self._do_cmd_no_resp(TeledyneInstrumentCmds.START_LOGGING, timeout=timeout)

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


        # Send break twice, as sometimes the driver ack's the first one then 
        # forgets to actually break.
        self._send_break(duration=500)
        time.sleep(2)
        self._send_break(duration=500)
        time.sleep(2)
        # Prompt device until command prompt is seen.
        timeout = 3
        self._wakeup_until(timeout, TeledynePrompt.COMMAND)

        # set logging to false, as we just got a prompt after a break
        logging = False

        if self._is_logging(timeout):
            log.debug("FAILED TO STOP LOGGING")
            raise InstrumentProtocolException("failed to stop logging")

        return True

    def _sanitize(self, s):
        s = s.replace('\xb3', '_')
        s = s.replace('\xbf', '_')
        s = s.replace('\xc0', '_')
        s = s.replace('\xd9', '_')
        s = s.replace('\xda', '_')
        s = s.replace('\xf8', '_')

        return s

    ########################################################################
    # handlers.
    ########################################################################

    def _handler_command_run_test_200(self, *args, **kwargs):
        """
        run test PT200
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.RUN_TEST_200, *args, **kwargs)

        return (next_state, result)

    def _handler_command_factory_sets(self, *args, **kwargs):
        """
        run test PT200
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.FACTORY_SETS, *args, **kwargs)

        return (next_state, result)

    def _handler_command_user_sets(self, *args, **kwargs):
        """
        run test PT200
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.USER_SETS, *args, **kwargs)

        return (next_state, result)

    def _handler_command_get_instrument_transform_matrix(self, *args, **kwargs):
        """
        save setup to ram.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.GET_INSTRUMENT_TRANSFORM_MATRIX, *args, **kwargs)

        return (next_state, result)

    def _handler_command_save_setup_to_ram(self, *args, **kwargs):
        """
        save setup to ram.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.SAVE_SETUP_TO_RAM, *args, **kwargs)

        return (next_state, result)

    def _handler_command_clear_error_status_word(self, *args, **kwargs):
        """
        clear the error status word
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.CLEAR_ERROR_STATUS_WORD, *args, **kwargs)
        return (next_state, result)

    def _handler_command_acquire_error_status_word(self, *args, **kwargs):
        """
        read the error status word
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.DISPLAY_ERROR_STATUS_WORD, *args, **kwargs)
        return (next_state, result)

    def _handler_command_display_fault_log(self, *args, **kwargs):
        """
        display the error log.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.GET_FAULT_LOG, *args, **kwargs)
        return (next_state, result)

    def _handler_command_clear_fault_log(self, *args, **kwargs):
        """
        clear the error log.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.CLEAR_FAULT_LOG, *args, **kwargs)
        return (next_state, result)

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to initialize parameters and send a config change event.
        self._protocol_fsm.on_event(TeledyneProtocolEvent.INIT_PARAMS)
     
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)


        log.trace("in _handler_command_enter()")
        #self._update_params()

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
        @retval (next_state, result), (SBE37ProtocolState.COMMAND or
        SBE37State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """
        (protocol_state, agent_state) = self._discover()

        if(protocol_state == TeledyneProtocolState.COMMAND):
            agent_state = ResourceAgentState.IDLE

        return (protocol_state, agent_state)

    ######################################################
    #                                                    #
    ######################################################
    def _handler_command_init_params(self, *args, **kwargs):
        """
        initialize parameters
        """
        next_state = None
        result = None
     
        self._init_params()
        return (next_state, result)

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        self._protocol_fsm.on_event(TeledyneProtocolEvent.INIT_PARAMS)
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state.
        """
        log.trace("IN _handler_autosample_exit")

        pass
    
    def _handler_autosample_init_params(self, *args, **kwargs):
        """
        initialize parameters.  For this instrument we need to
        put the instrument into command mode, apply the changes
        then put it back.
        """
        log.debug("in _handler_autosample_init_params")
        next_state = None
        result = None
        error = None

        try:
            log.debug("stopping logging without checking")
            self._stop_logging()
            self._init_params()

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            log.debug("starting logging")
            self._start_logging()
                #self._do_cmd_no_resp(TeledyneInstrumentCmds.START_LOGGING)

        if (error):
            log.error("Error in apply_startup_params: %s", error)
            raise error

        return (next_state, result)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        result = None
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        kwargs['timeout'] = 30

        log.info("SYNCING TIME WITH SENSOR.")
        resp = self._do_cmd_resp(TeledyneInstrumentCmds.SET, TeledyneParameter.TIME, get_timestamp_delayed("%Y/%m/%d, %H:%M:%S"), **kwargs)

        # Save setup to nvram and switch to autosample if successful.
        resp = self._do_cmd_resp(TeledyneInstrumentCmds.SAVE_SETUP_TO_RAM, *args, **kwargs)

        # Issue start command and switch to autosample if successful.
        self._start_logging()

        next_state = TeledyneProtocolState.AUTOSAMPLE
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

        #if (self._is_logging(timeout)):
        self._stop_logging(timeout)

        next_state = TeledyneProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    def _handler_command_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @throws InstrumentParameterException if missing or invalid parameter.
        """
        log.trace("in _handler_command_get")
        next_state = None
        result = None
        error = None

        # Grab a baseline time for calculating expiration time.  It is assumed
        # that all data if valid if acquired after this time.
        expire_time = self._param_dict.get_current_timestamp()
        log.trace("expire_time = " + str(expire_time))
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

            log.trace("in _handler_command_get Parameter expired, refreshing, %s", e)

            if self._is_logging():
                log.trace("I am logging")
                try:
                    # Switch to command mode,
                    self._stop_logging()

                    self._update_params()
                    # Take a second pass at getting values, this time is should
                    # have all fresh values.
                    log.trace("Fetching parameters for the second time")
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
                log.trace("I am not logging")
                self._update_params()
                # Take a second pass at getting values, this time is should
                # have all fresh values.
                log.trace("Fetching parameters for the second time")
                result = self._get_param_result(param_list, expire_time)
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
            output = self._do_cmd_resp(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)


        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging()

        if(error):
            raise error
     
        result = self._sanitize(base64.b64decode(output))
        return (next_state, (next_agent_state, result))
        #return (next_state, (next_agent_state, {'result': result}))

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
            output = self._do_cmd_resp(TeledyneInstrumentCmds.GET_SYSTEM_CONFIGURATION, *args, **kwargs)

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging()

        if(error):
            raise error
        
        result = self._sanitize(base64.b64decode(output))
        
        return (next_state, (next_agent_state, result))
        

    def _handler_recover_autosample(self, *args, **kwargs):
        """
        Reenter autosample mode.  Used when our data handler detects
        as data sample.
        @retval (next_state, result) tuple, (None, sample dict).
        """
        next_state = TeledyneProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING
        result = None

        self._async_agent_state_change(ResourceAgentState.STREAMING)

        return (next_state, next_agent_state)


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
        
        logging = False
        
        self._promptbuf = ""
        self._linebuf = ""
        
        if self._is_logging():
            logging = True
            # Switch to command mode,
            self._stop_logging()
            
        log.debug("in _handler_autosample_clock_sync")
        try:
            # Sync the clock
            timeout = kwargs.get('timeout', TIMEOUT)

            self._sync_clock(TeledyneInstrumentCmds.SET, TeledyneParameter.TIME, timeout, time_format="%Y/%m/%d,%H:%M:%S")

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            if logging:
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
        log.trace("IN _handler_command_set")
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

    def _handler_command_get_calibration(self, *args, **kwargs):
        """
        @param args:
        @param kwargs:
        @return:
        """
        log.trace("IN _handler_command_get_calibration")
        next_state = None
        next_agent_state = None
        result = None

        kwargs['timeout'] = 120

        output = self._do_cmd_resp(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)
        result = self._sanitize(base64.b64decode(output))
        return (next_state, (next_agent_state, result))

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
        log.debug("in _handler_command_get_configuration")
        output = self._do_cmd_resp(TeledyneInstrumentCmds.GET_SYSTEM_CONFIGURATION, *args, **kwargs)
        result = self._sanitize(base64.b64decode(output))
        return (next_state, (next_agent_state, {'result': result}))

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
        prompt = self._wakeup(timeout=3)
        self._sync_clock(TeledyneInstrumentCmds.SET, TeledyneParameter.TIME, timeout, time_format="%Y/%m/%d,%H:%M:%S")
        return (next_state, (next_agent_state, result))

    def _handler_command_send_last_sample(self, *args, **kwargs):
        log.debug("IN _handler_command_send_last_sample")

        next_state = None
        next_agent_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = '>\r\n>' # special one off prompt.
        prompt = self._wakeup(timeout=3)

        # Disable autosample recover, so it isnt faked out....
        self.disable_autosample_recover = True
        (result, last_sample) = self._do_cmd_resp(TeledyneInstrumentCmds.SEND_LAST_SAMPLE, *args, **kwargs)
        # re-enable it.
        self.disable_autosample_recover = False

        decoded_last_sample = base64.b64decode(last_sample)

        return (next_state, (next_agent_state, decoded_last_sample))

    def _handler_command_start_direct(self, *args, **kwargs):
        next_state = None
        result = None
        log.debug("_handler_command_start_direct: entering DA mode")

        next_state = TeledyneProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
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
        log.debug("IN _handler_direct_access_exit")
        self._send_break()

        result = self._do_cmd_resp(TeledyneInstrumentCmds.GET, TeledyneParameter.TIME_OF_FIRST_PING)
        if "****/**/**,**:**:**" not in result:
            log.error("TG not allowed to be set. sending a break to clear it.")

            self._send_break()

    def _handler_direct_access_execute_direct(self, data):
        log.debug("IN _handler_direct_access_execute_direct")
        next_state = None
        result = None
        next_agent_state = None
        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return (next_state, (next_agent_state, result))

    def _discover(self):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE or UNKNOWN.
        @retval (next_protocol_state, next_agent_state)
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """
        log.debug("IN _discover")
        logging = self._is_logging()
        log.error("LOGGING = " + str(logging))
        if (logging == True):
            return (TeledyneProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING)
        elif (logging == False):
            return (TeledyneProtocolState.COMMAND, ResourceAgentState.COMMAND)
        else:
            return (TeledyneProtocolState.UNKNOWN, ResourceAgentState.ACTIVE_UNKNOWN)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None
        log.debug("IN _handler_direct_access_stop_direct")
        (next_state, next_agent_state) = self._discover()

        return (next_state, (next_agent_state, result))

    def _handler_command_restore_factory_params(self):
        """
        """

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
            log.trace("IN _build_set_command CMD = '%s'", set_cmd)
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

        if prompt == TeledynePrompt.ERR:
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

        kwargs['expected_prompt'] = TeledynePrompt.COMMAND + NEWLINE + TeledynePrompt.COMMAND
        try:
            self.get_param = param
            get_cmd = param + '?' + NEWLINE
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return get_cmd

    def _parse_get_response(self, response, prompt):
        log.trace("GET RESPONSE = " + repr(response))
        if prompt == TeledynePrompt.ERR:
            raise InstrumentProtocolException('Protocol._parse_set_response : Set command not recognized: %s' % response)

        while (not response.endswith('\r\n>\r\n>')) or ('?' not in response):
            (prompt, response) = self._get_raw_response(30, TeledynePrompt.COMMAND)
            time.sleep(.05) # was 1

        self._param_dict.update(response)

        for line in response.split(NEWLINE):
            self._param_dict.update(line)
            if not "?" in line and ">" != line:
                response = line

        if self.get_param not in response:
            raise InstrumentParameterException('Failed to get a response for lookup of ' + self.get_param)

        self.get_count = 0
        return response

    ########################################################################
    # response handlers.
    ########################################################################
    ### Not sure if these are needed, since I'm creating data particles
    ### for the information.

    def _parse_output_calibration_data_response(self, response, prompt):
        """
        Return the output from the calibration request base 64 encoded
        """
        log.debug("in _parse_output_calibration_data_response")
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
        log.trace("parse_error_status_response = %s", str(response))
        response = re.sub("CY0\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return (True, response)

    def _parse_error_status_response(self, response, prompt):
        """
        get the error status word, it should be 8 bytes of hexidecimal.
        """

        log.trace("parse_error_status_response = %s", str(response))
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
        
    def _parse_restore_factory_params_response(self):
        """
        """
    ########################################################################
    # Static helpers to format set commands.
    ########################################################################

    @staticmethod
    def _bool_to_int(v):
        """
        Write a bool value to string as an int.
        @param v A bool val.
        @retval a int string.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v, int):
            raise InstrumentParameterException('Value %s is not a int.' % v)
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
                log.trace("RETURNING 0")
                return 0
            else:
                log.trace("RETURNING 1")
                return 1

