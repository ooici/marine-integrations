"""
@package mi.instrument.teledyne.driver
@file marine-integrations/mi/instrument/teledyne/driver.py
@author Sung Ahn
@brief Driver for the teledyne family
Release notes:
"""

__author__ = 'Sung Ahn'
__license__ = 'Apache 2.0'

import re
import base64
import time

from mi.core.common import BaseEnum
from mi.core.time import get_timestamp_delayed

from mi.core.exceptions import InstrumentParameterException, NotImplementedException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException

from mi.core.log import get_logger
log = get_logger()
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver, DriverConnectionState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.util import dict_equal


# default timeout.
TIMEOUT = 20

# newline.
NEWLINE = '\r\n'

DEFAULT_CMD_TIMEOUT = 20
DEFAULT_WRITE_DELAY = 0

ZERO_TIME_INTERVAL = '00:00:00'


class TeledynePrompt(BaseEnum):
    """
    Device i/o prompts..
    """
    COMMAND = '\r\n>\r\n>'
    ERR = 'ERR:'


class TeledyneParameter(DriverParameter):
    """
    Device parameters
    """
    #
    # set-able parameters
    #
    SERIAL_DATA_OUT = 'CD'  # 000 000 000 Serial Data Out (Vel;Cor;Amp PG;St;P0 P1;P2;P3)
    INSTRUMENT_ID = 'CI'  # Int 0-255
    XMIT_POWER = 'CQ'  # 0=Low, 255=High
    SPEED_OF_SOUND = 'EC'  # 1500  Speed Of Sound (m/s)
    SALINITY = 'ES'  # 35 (0-40 pp thousand)
    COORDINATE_TRANSFORMATION = 'EX'  #
    SENSOR_SOURCE = 'EZ'  # Sensor Source (C;D;H;P;R;S;T)
    TIME_PER_ENSEMBLE = 'TE'  # 01:00:00.00 (hrs:min:sec.sec/100)
    TIME_OF_FIRST_PING = 'TG'  # ****/**/**,**:**:** (CCYY/MM/DD,hh:mm:ss)
    TIME_PER_PING = 'TP'  # 00:00.20  (min:sec.sec/100)
    TIME = 'TT'  # 2013/02/26,05:28:23 (CCYY/MM/DD,hh:mm:ss)
    FALSE_TARGET_THRESHOLD = 'WA'  # 255,001 (Max)(0-255),Start Bin # <--------- TRICKY.... COMPLEX TYPE
    BANDWIDTH_CONTROL = 'WB'  # Bandwidth Control (0=Wid,1=Nar)
    CORRELATION_THRESHOLD = 'WC'  # 064  Correlation Threshold
    SERIAL_OUT_FW_SWITCHES = 'WD'  # 111100000  Data Out (Vel;Cor;Amp PG;St;P0 P1;P2;P3)
    ERROR_VELOCITY_THRESHOLD = 'WE'  # 5000  Error Velocity Threshold (0-5000 mm/s)
    BLANK_AFTER_TRANSMIT = 'WF'  # 0088  Blank After Transmit (cm)
    CLIP_DATA_PAST_BOTTOM = 'WI'  # 0 Clip Data Past Bottom (0=OFF,1=ON)
    RECEIVER_GAIN_SELECT = 'WJ'  # 1  Rcvr Gain Select (0=Low,1=High)
    NUMBER_OF_DEPTH_CELLS = 'WN'  # Number of depth cells (1-255)
    PINGS_PER_ENSEMBLE = 'WP'  # Pings per Ensemble (0-16384)
    DEPTH_CELL_SIZE = 'WS'  # 0800  Depth Cell Size (cm)
    TRANSMIT_LENGTH = 'WT'  # 0000 Transmit Length 0 to 3200(cm) 0 = Bin Length
    PING_WEIGHT = 'WU'  # 0 Ping Weighting (0=Box,1=Triangle)
    AMBIGUITY_VELOCITY = 'WV'  # 175 Mode 1 Ambiguity Vel (cm/s radial)

    #
    # Workhorse parameters
    #
    SERIAL_FLOW_CONTROL = 'CF'  # Flow Control
    BANNER = 'CH'  # Banner
    SLEEP_ENABLE = 'CL'  # SLEEP Enable
    SAVE_NVRAM_TO_RECORDER = 'CN'  # Save NVRAM to RECORD
    POLLED_MODE = 'CP'  # Polled Mode
    PITCH = 'EP'  # Pitch
    ROLL = 'ER'  # Roll

    LATENCY_TRIGGER = 'CX'  # Latency Trigger
    HEADING_ALIGNMENT = 'EA'  # Heading Alignment
    HEADING_BIAS = 'EB'  # Heading Bias
    DATA_STREAM_SELECTION = 'PD'  # Data Stream selection
    ENSEMBLE_PER_BURST = 'TC'  # Ensemble per Burst
    BUFFERED_OUTPUT_PERIOD = 'TX'  # Buffered Output Period
    SAMPLE_AMBIENT_SOUND = 'WQ'  # Sample Ambient sound
    TRANSDUCER_DEPTH = 'ED'  # Transducer Depth

    # Engineering parameters for the scheduled commands
    CLOCK_SYNCH_INTERVAL = 'clockSynchInterval'
    GET_STATUS_INTERVAL = 'getStatusInterval'


class TeledyneInstrumentCmds(BaseEnum):
    """
    Device specific commands
    Represents the commands the driver implements and the string that
    must be sent to the instrument to execute the command.
    """

    OUTPUT_CALIBRATION_DATA = 'AC'
    BREAK = 'break'  # < case sensitive!!!!
    SAVE_SETUP_TO_RAM = 'CK'
    FACTORY_SETS = 'CR1'  # Factory default set
    USER_SETS = 'CR0'  # User default set
    START_LOGGING = 'CS'
    CLEAR_ERROR_STATUS_WORD = 'CY0'  # May combine with next
    DISPLAY_ERROR_STATUS_WORD = 'CY1'  # May combine with prior
    CLEAR_FAULT_LOG = 'FC'
    GET_FAULT_LOG = 'FD'

    GET_SYSTEM_CONFIGURATION = 'PS0'
    RUN_TEST_200 = 'PT200'
    SET = 'set'  # leading spaces are OK. set is just PARAM_NAME next to VALUE
    GET = 'get '
    OUTPUT_PT2 = 'PT2'
    OUTPUT_PT4 = 'PT4'


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

    SAVE_SETUP_TO_RAM = "PROTOCOL_EVENT_SAVE_SETUP_TO_RAM"

    GET_ERROR_STATUS_WORD = "PROTOCOL_EVENT_GET_ERROR_STATUS_WORD"
    CLEAR_ERROR_STATUS_WORD = "PROTOCOL_EVENT_CLEAR_ERROR_STATUS_WORD"

    GET_FAULT_LOG = "PROTOCOL_EVENT_GET_FAULT_LOG"
    CLEAR_FAULT_LOG = "PROTOCOL_EVENT_CLEAR_FAULT_LOG"

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
    SCHEDULED_GET_STATUS = 'PROTOCOL_EVENT_SCHEDULED_GET_STATUS'
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC

    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    RECOVER_AUTOSAMPLE = 'PROTOCOL_EVENT_RECOVER_AUTOSAMPLE'
    RESTORE_FACTORY_PARAMS = "PROTOCOL_EVENT_RESTORE_FACTORY_PARAMS"

    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS  # The command will execute "AC, PT2, PT4"


class TeledyneCapability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = TeledyneProtocolEvent.CLOCK_SYNC
    GET_CALIBRATION = TeledyneProtocolEvent.GET_CALIBRATION
    RUN_TEST_200 = TeledyneProtocolEvent.RUN_TEST_200
    ACQUIRE_STATUS = TeledyneProtocolEvent.ACQUIRE_STATUS


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
        # Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED,
                                         DriverEvent.DISCOVER,
                                         self._handler_connected_discover)

    def _handler_connected_discover(self, event, *args, **kwargs):
        # Redefine discover handler so that we can apply startup params
        # when we discover. Gotta get into command mode first though.
        result = SingleConnectionInstrumentDriver._handler_connected_protocol_event(self, event, *args, **kwargs)
        self.apply_startup_params()
        return result


# noinspection PyMethodMayBeStatic
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
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        self.last_wakeup = 0

        # Build ADCPT protocol state machine.
        self._protocol_fsm = ThreadSafeFSM(TeledyneProtocolState, TeledyneProtocolEvent,
                                           TeledyneProtocolEvent.ENTER, TeledyneProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(TeledyneProtocolState.UNKNOWN, TeledyneProtocolEvent.ENTER,
                                       self._handler_unknown_enter)
        self._protocol_fsm.add_handler(TeledyneProtocolState.UNKNOWN, TeledyneProtocolEvent.EXIT,
                                       self._handler_unknown_exit)
        self._protocol_fsm.add_handler(TeledyneProtocolState.UNKNOWN, TeledyneProtocolEvent.DISCOVER,
                                       self._handler_unknown_discover)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.ENTER,
                                       self._handler_command_enter)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.EXIT,
                                       self._handler_command_exit)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.INIT_PARAMS,
                                       self._handler_command_init_params)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.GET,
                                       self._handler_get)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.START_AUTOSAMPLE,
                                       self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.SET,
                                       self._handler_command_set)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.CLOCK_SYNC,
                                       self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.SCHEDULED_CLOCK_SYNC,
                                       self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.SCHEDULED_GET_STATUS,
                                       self._handler_command_get_status)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.GET_CALIBRATION,
                                       self._handler_command_get_calibration)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.GET_CONFIGURATION,
                                       self._handler_command_get_configuration)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.SAVE_SETUP_TO_RAM,
                                       self._handler_command_save_setup_to_ram)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.START_DIRECT,
                                       self._handler_command_start_direct)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.RUN_TEST_200,
                                       self._handler_command_run_test_200)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.FACTORY_SETS,
                                       self._handler_command_factory_sets)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.USER_SETS,
                                       self._handler_command_user_sets)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.GET_ERROR_STATUS_WORD,
                                       self._handler_command_acquire_error_status_word)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.CLEAR_ERROR_STATUS_WORD,
                                       self._handler_command_clear_error_status_word)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.CLEAR_FAULT_LOG,
                                       self._handler_command_clear_fault_log)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.GET_FAULT_LOG,
                                       self._handler_command_display_fault_log)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.ACQUIRE_STATUS,
                                       self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.ENTER,
                                       self._handler_autosample_enter)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.EXIT,
                                       self._handler_autosample_exit)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.INIT_PARAMS,
                                       self._handler_autosample_init_params)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.STOP_AUTOSAMPLE,
                                       self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.GET,
                                       self._handler_get)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.SCHEDULED_CLOCK_SYNC,
                                       self._handler_autosample_clock_sync)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.SCHEDULED_GET_STATUS,
                                       self._handler_autosample_get_status)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.GET_CALIBRATION,
                                       self._handler_autosample_get_calibration)
        self._protocol_fsm.add_handler(TeledyneProtocolState.AUTOSAMPLE, TeledyneProtocolEvent.GET_CONFIGURATION,
                                       self._handler_autosample_get_configuration)
        self._protocol_fsm.add_handler(TeledyneProtocolState.COMMAND, TeledyneProtocolEvent.RECOVER_AUTOSAMPLE,
                                       self._handler_recover_autosample)

        self._protocol_fsm.add_handler(TeledyneProtocolState.DIRECT_ACCESS, TeledyneProtocolEvent.ENTER,
                                       self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(TeledyneProtocolState.DIRECT_ACCESS, TeledyneProtocolEvent.EXIT,
                                       self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(TeledyneProtocolState.DIRECT_ACCESS, TeledyneProtocolEvent.EXECUTE_DIRECT,
                                       self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(TeledyneProtocolState.DIRECT_ACCESS, TeledyneProtocolEvent.STOP_DIRECT,
                                       self._handler_direct_access_stop_direct)

        # Build dictionaries for driver schema
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        # Add build handlers for device commands.
        self._add_build_handler(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.SAVE_SETUP_TO_RAM, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.START_LOGGING, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.DISPLAY_ERROR_STATUS_WORD, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.CLEAR_ERROR_STATUS_WORD, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.CLEAR_FAULT_LOG, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.GET_FAULT_LOG, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.GET_SYSTEM_CONFIGURATION, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.RUN_TEST_200, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.FACTORY_SETS, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.USER_SETS, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.SET, self._build_set_command)
        self._add_build_handler(TeledyneInstrumentCmds.GET, self._build_get_command)
        self._add_build_handler(TeledyneInstrumentCmds.OUTPUT_PT2, self._build_simple_command)
        self._add_build_handler(TeledyneInstrumentCmds.OUTPUT_PT4, self._build_simple_command)
        self._add_response_handler(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA,
                                   self._parse_output_calibration_data_response)
        self._add_response_handler(TeledyneInstrumentCmds.SAVE_SETUP_TO_RAM, self._parse_save_setup_to_ram_response)
        self._add_response_handler(TeledyneInstrumentCmds.CLEAR_ERROR_STATUS_WORD,
                                   self._parse_clear_error_status_response)
        self._add_response_handler(TeledyneInstrumentCmds.DISPLAY_ERROR_STATUS_WORD, self._parse_error_status_response)
        self._add_response_handler(TeledyneInstrumentCmds.CLEAR_FAULT_LOG, self._parse_clear_fault_log_response)
        self._add_response_handler(TeledyneInstrumentCmds.GET_FAULT_LOG, self._parse_fault_log_response)
        self._add_response_handler(TeledyneInstrumentCmds.GET_SYSTEM_CONFIGURATION,
                                   self._parse_get_system_configuration)
        self._add_response_handler(TeledyneInstrumentCmds.RUN_TEST_200, self._parse_test_response)

        self._add_response_handler(TeledyneInstrumentCmds.FACTORY_SETS, self._parse_factory_set_response)
        self._add_response_handler(TeledyneInstrumentCmds.USER_SETS, self._parse_user_set_response)

        self._add_response_handler(TeledyneInstrumentCmds.SET, self._parse_set_response)
        self._add_response_handler(TeledyneInstrumentCmds.GET, self._parse_get_response)

        self._add_response_handler(TeledyneInstrumentCmds.OUTPUT_PT2, self._parse_output_calibration_data_response)
        self._add_response_handler(TeledyneInstrumentCmds.OUTPUT_PT4, self._parse_output_calibration_data_response)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(TeledyneProtocolState.UNKNOWN)

        # commands sent sent to device to be
        # filtered in responses for telnet DA
        self._sent_cmds = []

        self.disable_autosample_recover = False

    def stop_scheduled_job(self, schedule_job):
        """
        Remove the scheduled job
        @param schedule_job scheduling job.
        """
        log.debug("Attempting to remove the scheduler")
        if self._scheduler is not None:
            try:
                self._remove_scheduler(schedule_job)
                log.debug("successfully removed scheduler")
            except KeyError:
                log.debug("_remove_scheduler could not find %s", schedule_job)

    def start_scheduled_job(self, param, schedule_job, protocol_event):
        """
        Add a scheduled job
        """
        self.stop_scheduled_job(schedule_job)

        interval = self._param_dict.get(param).split(':')
        hours = interval[0]
        minutes = interval[1]
        seconds = interval[2]
        log.debug("Setting scheduled interval to: %s %s %s", hours, minutes, seconds)

        if hours == '00' and minutes == '00' and seconds == '00':
            # if interval is all zeroed, then stop scheduling jobs
            self.stop_scheduled_job(schedule_job)
        else:
            config = {DriverConfigKey.SCHEDULER: {
                schedule_job: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.HOURS: int(hours),
                        DriverSchedulerConfigKey.MINUTES: int(minutes),
                        DriverSchedulerConfigKey.SECONDS: int(seconds)
                    }
                }
            }
            }
            self.set_init_params(config)
            self._add_scheduler_event(schedule_job, protocol_event)

    def _build_param_dict(self):
        """
        It will be implemented in its child
        @throw NotImplementedException
        """
        raise NotImplementedException('Not implemented.')

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if TeledyneCapability.has(x)]

    def _sync_clock(self, command, date_time_param, timeout=TIMEOUT, delay=1, time_format="%d %b %Y %H:%M:%S"):
        """
        Send the command to the instrument to synchronize the clock
        @param command set command
        @param date_time_param: date time parameter that we want to set
        @param timeout: command timeout
        @param delay: wakeup delay
        @param time_format: time format string for set command
        """
        self._wakeup(timeout=3, delay=delay)

        # lets clear out any past data so it doesnt confuse the command
        self._linebuf = ''
        self._promptbuf = ''

        self._wakeup(timeout=3, delay=delay)
        str_val = get_timestamp_delayed(time_format)
        self._do_cmd_direct(date_time_param + str_val)
        time.sleep(1)
        self._get_response(TIMEOUT)

    # #######################################################################
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
        if (self.get_current_state() != TeledyneProtocolState.COMMAND and
                    self.get_current_state() != TeledyneProtocolState.AUTOSAMPLE):
            raise InstrumentProtocolException("Not in command or autosample state. Unable to apply startup params")

        logging = self._is_logging()
        # If we are in streaming mode and our configuration on the
        # instrument matches what we think it should be then we
        # don't need to do anything.

        if not self._instrument_config_dirty():
            return True

        error = None

        try:
            if logging:
                # Switch to command mode,
                self._stop_logging()

            self._apply_params()

        # Catch all error so we can put ourselves back into
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

        if error:
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

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary.
        """
        log.debug("in _update_params")
        error = None
        logging = self._is_logging()
        results = None

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
                if attr not in ['dict', 'has', 'list', 'ALL', 'GET_STATUS_INTERVAL', 'CLOCK_SYNCH_INTERVAL']:
                    if not attr.startswith("_"):
                        key = self._getattr_key(attr)
                        result = self._do_cmd_resp(TeledyneInstrumentCmds.GET, key, **kwargs)
                        results += result + NEWLINE

            new_config = self._param_dict.get_config()

            # Check if there is any changes. Ignore TT
            if not dict_equal(new_config, old_config, ['TT']):
                self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

        # Catch all error so we can put ourselves back into
        # streaming.  Then rethrow the error
        except Exception as e:
            log.error("EXCEPTION in _update_params WAS " + str(e))
            error = e

        finally:
            # Switch back to streaming
            if logging:
                log.debug("GOING BACK INTO LOGGING")
                my_state = self._protocol_fsm.get_current_state()
                log.debug("current_state = %s calling start_logging", my_state)
                self._start_logging()

        if error:
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
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        log.trace("_set_params calling _verify_not_readonly ARGS = " + repr(args))
        self._verify_not_readonly(*args, **kwargs)
        for key, val in params.iteritems():
            if key.find('_') == -1:  # Not found, Master parameters
                if key not in [TeledyneParameter.CLOCK_SYNCH_INTERVAL, TeledyneParameter.GET_STATUS_INTERVAL]:
                    result = self._do_cmd_resp(TeledyneInstrumentCmds.SET, key, val, **kwargs)
        log.trace("_set_params calling _update_params")
        self._update_params()
        return result

    # This method will be overwritten
    def _send_break_cmd(self, duration=500):
        """
        Send a BREAK to attempt to wake the device.
        """
        log.error("SENDING BREAK TO PORT AGENT is not implemented")
        raise NotImplementedException('SENDING BREAK TO PORT AGENT is not implemented')

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

        break_confirmation.append("[BREAK Wakeup A]")
        found = False
        timeout = 30
        count = 0
        while not found:
            count += 1
            for break_message in break_confirmation:
                if break_message in self._linebuf:
                    log.trace("GOT A BREAK MATCH ==> " + str(break_message))
                    found = True
            if count > (timeout * 10):
                if not found:
                    raise InstrumentTimeoutException("NO BREAK RESPONSE..")
            time.sleep(0.1)
        self._chunker.clean_all_chunks()
        self._promptbuf = ''
        self._linebuf = ''

    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the device.
        """

        self._connection.send(NEWLINE)

    def _wakeup(self, timeout=3, delay=1):
        """
        Clear buffers and send a wakeup command to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
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
                raise InstrumentParameterException("A param is unknown")

            if self._param_dict.get(param) != self._param_dict.get_config_value(param):
                log.trace("DIRTY: %s %s != %s" % (
                    param, self._param_dict.get(param), self._param_dict.get_config_value(param)))
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

        self._linebuf = ""
        self._promptbuf = ""

        prompt = self._wakeup(timeout=3)
        if TeledynePrompt.COMMAND == prompt:
            logging = False
        else:
            logging = True

        return logging

    def _start_logging(self, timeout=TIMEOUT):
        """
        Command the instrument to start logging
        @param timeout: how long to wait for a prompt
        @throws: InstrumentProtocolException if failed to start logging
        """
        if self._is_logging():
            return True
        self._do_cmd_no_resp(TeledyneInstrumentCmds.START_LOGGING, timeout=timeout)

    def _stop_logging(self, timeout=TIMEOUT):
        """
        Command the instrument to stop logging
        @param timeout: how long to wait for a prompt
        @throws: InstrumentTimeoutException if prompt isn't seen
        @throws: InstrumentProtocolException failed to stop logging
        """
        # Issue the stop command.

        # Send break twice, as sometimes the driver ack's the first one then
        # forgets to actually break.
        self._wakeup()
        self._send_break(duration=3000)
        time.sleep(2)

        # Prompt device until command prompt is seen.
        timeout = 3
        self._wakeup_until(timeout, TeledynePrompt.COMMAND)
        # set logging to false, as we just got a prompt after a break

        if self._is_logging(timeout):
            log.error("FAILED TO STOP LOGGING in _stop_logging")
            raise InstrumentProtocolException("failed to stop logging")

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
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.RUN_TEST_200, *args, **kwargs)

        return next_state, result

    def _handler_command_factory_sets(self, *args, **kwargs):
        """
        run Factory set
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.FACTORY_SETS, *args, **kwargs)

        return next_state, result

    def _handler_command_user_sets(self, *args, **kwargs):
        """
        run user set
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.USER_SETS, *args, **kwargs)

        return next_state, result

    def _handler_command_save_setup_to_ram(self, *args, **kwargs):
        """
        save setup to ram.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.SAVE_SETUP_TO_RAM, *args, **kwargs)

        return next_state, result

    def _handler_command_clear_error_status_word(self, *args, **kwargs):
        """
        clear the error status word
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.CLEAR_ERROR_STATUS_WORD, *args, **kwargs)
        return next_state, result

    def _handler_command_acquire_error_status_word(self, *args, **kwargs):
        """
        read the error status word
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.DISPLAY_ERROR_STATUS_WORD, *args, **kwargs)
        return next_state, result

    def _handler_command_display_fault_log(self, *args, **kwargs):
        """
        display the error log.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.GET_FAULT_LOG, *args, **kwargs)
        return next_state, result

    def _handler_command_clear_fault_log(self, *args, **kwargs):
        """
        clear the error log.
        """
        next_state = None
        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        result = self._do_cmd_resp(TeledyneInstrumentCmds.CLEAR_FAULT_LOG, *args, **kwargs)
        return next_state, result

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

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        # start scheduled event for clock synch only if the interval is not "00:00:00
        clock_interval = self._param_dict.get(TeledyneParameter.CLOCK_SYNCH_INTERVAL)
        if clock_interval != ZERO_TIME_INTERVAL:
            self.start_scheduled_job(TeledyneParameter.CLOCK_SYNCH_INTERVAL, TeledyneScheduledJob.CLOCK_SYNC,
                                     TeledyneProtocolEvent.SCHEDULED_CLOCK_SYNC)

        # start scheduled event for get_status only if the interval is not "00:00:00
        status_interval = self._param_dict.get(TeledyneParameter.GET_STATUS_INTERVAL)
        if status_interval != ZERO_TIME_INTERVAL:
            self.start_scheduled_job(TeledyneParameter.GET_STATUS_INTERVAL, TeledyneScheduledJob.GET_CONFIGURATION,
                                     TeledyneProtocolEvent.SCHEDULED_GET_STATUS)

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

    ######################################################
    #                                                    #
    ######################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @return protocol_state, agent_state if successful
        """
        protocol_state, agent_state = self._discover()
        if protocol_state == TeledyneProtocolState.COMMAND:
            agent_state = ResourceAgentState.IDLE

        return protocol_state, agent_state

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
        return next_state, result

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

        # Catch all error so we can put ourselves back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            log.debug("starting logging")
            self._start_logging()

        if error:
            log.error("Error in apply_startup_params: %s", error)
            raise error

        return next_state, result

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @return next_state, (next_agent_state, result) if successful.
        """
        result = None
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND
        kwargs['timeout'] = 30

        log.info("SYNCING TIME WITH SENSOR.")
        self._do_cmd_resp(TeledyneInstrumentCmds.SET, TeledyneParameter.TIME,
                          get_timestamp_delayed("%Y/%m/%d, %H:%M:%S"), **kwargs)

        # Save setup to nvram and switch to autosample if successful.
        self._do_cmd_resp(TeledyneInstrumentCmds.SAVE_SETUP_TO_RAM, *args, **kwargs)

        # Issue start command and switch to autosample if successful.
        self._start_logging()

        next_state = TeledyneProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return next_state, (next_agent_state, result)

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @return  next_state, (next_agent_state, result) if successful.
        incorrect prompt received.
        """
        result = None

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', TIMEOUT)

        self._stop_logging(timeout)

        next_state = TeledyneProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return next_state, (next_agent_state, result)

    def _handler_autosample_get_calibration(self, *args, **kwargs):
        """
        execute a get calibration from autosample mode.
        For this command we have to move the instrument
        into command mode, get calibration, then switch back.  If an
        exception is thrown we will try to get ourselves back into
        streaming and then raise that exception.
        @return (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        next_agent_state = None
        output = ""
        error = None

        try:
            # Switch to command mode,
            self._stop_logging(*args, **kwargs)

            kwargs['timeout'] = 120
            output = self._do_cmd_resp(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)

        # Catch all error so we can put ourselves back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging()

        if error:
            raise error

        result = self._sanitize(base64.b64decode(output))
        return next_state, (next_agent_state, result)

    def _handler_autosample_get_configuration(self, *args, **kwargs):
        """
        execute a get configuration from autosample mode.
        For this command we have to move the instrument
        into command mode, get configuration, then switch back.  If an
        exception is thrown we will try to get ourselves back into
        streaming and then raise that exception.
        @return (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        output = ""
        error = None

        try:
            # Switch to command mode,
            self._stop_logging(*args, **kwargs)

            # Sync the clock
            output = self._do_cmd_resp(TeledyneInstrumentCmds.GET_SYSTEM_CONFIGURATION, *args, **kwargs)

        # Catch all error so we can put ourselves back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            self._start_logging()

        if error:
            raise error

        result = self._sanitize(base64.b64decode(output))

        return next_state, (next_agent_state, result)

    def _handler_recover_autosample(self, *args, **kwargs):
        """
        Reenter autosample mode.  Used when our data handler detects
        as data sample.
        @return next_state, next_agent_state
        """
        next_state = TeledyneProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        self._async_agent_state_change(ResourceAgentState.STREAMING)

        return next_state, next_agent_state

    def _handler_autosample_clock_sync(self, *args, **kwargs):
        """
        execute a clock sync on the leading edge of a second change from
        autosample mode.  For this command we have to move the instrument
        into command mode, do the clock sync, then switch back.  If an
        exception is thrown we will try to get ourselves back into
        streaming and then raise that exception.
        @return (next_state, (next_agent_state, result) if successful.
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

            self._sync_clock(TeledyneInstrumentCmds.SET, TeledyneParameter.TIME, timeout,
                             time_format="%Y/%m/%d,%H:%M:%S")

        # Catch all error so we can put ourselves back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            if logging:
                self._start_logging()

        if error:
            raise error

        return next_state, (next_agent_state, result)

    def _handler_command_set(self, *args, **kwargs):
        """
        Perform a set command.
        @param args[0] parameter : value dict.
        @return (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set parameters not ALL and
        not a dict, or if parameter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
        log.trace("IN _handler_command_set")
        next_state = None
        startup = False
        changed = False

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

        # Handle engineering parameters
        if TeledyneParameter.CLOCK_SYNCH_INTERVAL in params:
            if (params[TeledyneParameter.CLOCK_SYNCH_INTERVAL] != self._param_dict.get(
                    TeledyneParameter.CLOCK_SYNCH_INTERVAL)):
                self._param_dict.set_value(TeledyneParameter.CLOCK_SYNCH_INTERVAL,
                                           params[TeledyneParameter.CLOCK_SYNCH_INTERVAL])
                self.start_scheduled_job(TeledyneParameter.CLOCK_SYNCH_INTERVAL, TeledyneScheduledJob.CLOCK_SYNC,
                                         TeledyneProtocolEvent.SCHEDULED_CLOCK_SYNC)
                changed = True

        if TeledyneParameter.GET_STATUS_INTERVAL in params:
            if (params[TeledyneParameter.GET_STATUS_INTERVAL] != self._param_dict.get(
                    TeledyneParameter.GET_STATUS_INTERVAL)):
                self._param_dict.set_value(TeledyneParameter.GET_STATUS_INTERVAL,
                                           params[TeledyneParameter.GET_STATUS_INTERVAL])
                self.start_scheduled_job(TeledyneParameter.GET_STATUS_INTERVAL,
                                         TeledyneScheduledJob.GET_CONFIGURATION,
                                         TeledyneProtocolEvent.SCHEDULED_GET_STATUS)
                changed = True
        if changed:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        result = self._set_params(params, startup)

        return next_state, result

    def _handler_command_get_calibration(self, *args, **kwargs):
        """
        execute output_calibration_data command(AC)
        @return next_state, (next_agent_state, result)
        """
        log.trace("IN _handler_command_get_calibration")
        next_state = None
        next_agent_state = None

        kwargs['timeout'] = 120

        output = self._do_cmd_resp(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)
        result = self._sanitize(base64.b64decode(output))
        return next_state, (next_agent_state, result)

    def _handler_command_get_configuration(self, *args, **kwargs):
        """
        Get raw format of system configuration data
        @return next_state, (next_agent_state, {'result': result})
        """
        next_state = None
        next_agent_state = None

        kwargs['timeout'] = 120  # long time to get params.
        log.debug("in _handler_command_get_configuration")
        output = self._do_cmd_resp(TeledyneInstrumentCmds.GET_SYSTEM_CONFIGURATION, *args, **kwargs)
        result = self._sanitize(base64.b64decode(output))
        return next_state, (next_agent_state, {'result': result})

    def _handler_command_clock_sync(self, *args, **kwargs):
        """
        execute a clock sync on the leading edge of a second change
        @return next_state, (next_agent_state, result) if successful.
        """

        next_state = None
        next_agent_state = None
        result = None

        timeout = kwargs.get('timeout', TIMEOUT)
        self._wakeup(timeout=3)
        self._sync_clock(TeledyneInstrumentCmds.SET, TeledyneParameter.TIME, timeout, time_format="%Y/%m/%d,%H:%M:%S")
        return next_state, (next_agent_state, result)

    def _handler_command_get_status(self, *args, **kwargs):
        """
        execute a get status on the leading edge of a second change
        @return next_state, (next_agent_state, result) if successful.
        @throws InstrumentProtocolException from _do_cmd_no_resp.
        """

        next_state = None
        next_agent_state = None
        result = None

        try:
            # Get calibration, PT2 and PT4 events
            self._do_cmd_no_resp(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)
            self._do_cmd_no_resp(TeledyneInstrumentCmds.OUTPUT_PT2, *args, **kwargs)
            self._do_cmd_no_resp(TeledyneInstrumentCmds.OUTPUT_PT4, *args, **kwargs)

        except Exception as e:
            log.error("InstrumentProtocolException in _do_cmd_no_resp()")
            raise InstrumentProtocolException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

        return next_state, (next_agent_state, result)

    def _handler_autosample_get_status(self, *args, **kwargs):
        """
        execute a get status on the leading edge of a second change
        @return next_state, (next_agent_state, result) if successful.
        @throws InstrumentParameterException InstrumentParameterException from _do_cmd_no_resp
        """

        next_state = None
        next_agent_state = None
        result = None

        logging = False

        if self._is_logging():
            logging = True
            # Switch to command mode,
            self._stop_logging()
        try:
            self._do_cmd_no_resp(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)
            self._do_cmd_no_resp(TeledyneInstrumentCmds.OUTPUT_PT2, *args, **kwargs)
            self._do_cmd_no_resp(TeledyneInstrumentCmds.OUTPUT_PT4, *args, **kwargs)

        except Exception as e:
            log.error("InstrumentProtocolException in _do_cmd_no_resp()")
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp() :' + str(e))

        finally:
            # Switch back to streaming
            if logging:
                self._start_logging()
        return next_state, (next_agent_state, result)

    def _handler_command_start_direct(self, *args, **kwargs):
        result = None

        next_state = TeledyneProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        return next_state, (next_agent_state, result)

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
        self._send_break()

        result = self._do_cmd_resp(TeledyneInstrumentCmds.GET, TeledyneParameter.TIME_OF_FIRST_PING)
        if "****/**/**,**:**:**" not in result:
            log.error("TG not allowed to be set. sending a break to clear it.")

            self._send_break()

    def _handler_direct_access_execute_direct(self, data):
        next_state = None
        result = None
        next_agent_state = None
        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return next_state, (next_agent_state, result)

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Get the raw format outputs of the following commands, AC, PT2, PT4
        """
        log.debug("IN _handler_command_acquire_status")
        next_state = None

        kwargs['timeout'] = 30
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND

        try:
            self._do_cmd_no_resp(TeledyneInstrumentCmds.OUTPUT_CALIBRATION_DATA, *args, **kwargs)
            self._do_cmd_no_resp(TeledyneInstrumentCmds.OUTPUT_PT2, *args, **kwargs)
            self._do_cmd_no_resp(TeledyneInstrumentCmds.OUTPUT_PT4, *args, **kwargs)

        except Exception as e:
            raise InstrumentParameterException(
                'InstrumentProtocolException in _do_cmd_no_resp()' + str(e))

        return next_state, (None, None)

    def _discover(self):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE or UNKNOWN.
        @return (next_protocol_state, next_agent_state)
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """
        logging = self._is_logging()
        if logging:
            return TeledyneProtocolState.AUTOSAMPLE, ResourceAgentState.STREAMING
        return TeledyneProtocolState.COMMAND, ResourceAgentState.COMMAND

    def _handler_direct_access_stop_direct(self):
        """
        @reval next_state, (next_agent_state, result)
        """
        result = None
        (next_state, next_agent_state) = self._discover()

        return next_state, (next_agent_state, result)

    def _handler_command_restore_factory_params(self):
        """
        """

    def _build_set_command(self, cmd, param, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @return The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """

        try:
            str_val = self._param_dict.format(param, val)
            set_cmd = '%s%s' % (param, str_val) + NEWLINE
            log.trace("IN _build_set_command CMD = '%s'", set_cmd)
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter. %s' % param)

        return set_cmd

    def _parse_set_response(self, response, prompt):
        """
        Parse handler for set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """
        if prompt == TeledynePrompt.ERR:
            raise InstrumentParameterException(
                'Protocol._parse_set_response : Set command not recognized: %s' % response)

        if " ERR" in response:
            raise InstrumentParameterException('Protocol._parse_set_response : Set command failed: %s' % response)

    def _build_get_command(self, cmd, param, **kwargs):
        """
        param=val followed by newline.
        @param cmd get command
        @param param the parameter key to set.
        @param val the parameter value to set.
        @return The get command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        kwargs['expected_prompt'] = TeledynePrompt.COMMAND + NEWLINE + TeledynePrompt.COMMAND
        try:
            self.get_param = param
            get_cmd = param + '?' + NEWLINE
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter.. %s' % param)

        return get_cmd

    def _parse_get_response(self, response, prompt):
        log.trace("GET RESPONSE = " + repr(response))

        if prompt == TeledynePrompt.ERR:
            raise InstrumentProtocolException(
                'Protocol._parse_set_response : Set command not recognized: %s' % response)

        while (not response.endswith('\r\n>\r\n>')) or ('?' not in response):
            prompt, response = self._get_raw_response(30, TeledynePrompt.COMMAND)
            time.sleep(.05)  # was 1
        self._param_dict.update(response)

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
        return base64.b64encode(response)

    def _parse_get_system_configuration(self, response, prompt):
        """
        return the output from the get system configuration request base 64 encoded
        """
        return base64.b64encode(response)

    def _parse_save_setup_to_ram_response(self, response, prompt):
        """
        save settings to nv ram. return response.
        """
        # Cleanup the results
        response = re.sub("CK\r\n", "", response)
        response = re.sub("\[", "", response)
        response = re.sub("\]", "", response)
        response = re.sub("\r\n>", "", response)
        return True, response

    def _parse_clear_error_status_response(self, response, prompt):
        """
        Remove the sent command from the response and return it
        """
        response = re.sub("CY0\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return True, response

    def _parse_error_status_response(self, response, prompt):
        """
        get the error status word, it should be 8 bytes of hexidecimal.
        """

        response = re.sub("CY1\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return True, response

    def _parse_clear_fault_log_response(self, response, prompt):
        """
        clear the clear fault log.
        """
        response = re.sub("FC\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return True, response

    def _parse_fault_log_response(self, response, prompt):
        """
        display the fault log.
        """
        response = re.sub("FD\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return True, response

    def _parse_instrument_transform_matrix_response(self, response, prompt):
        """
        display the transform matrix.
        """
        response = re.sub("PS3\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return True, response

    def _parse_test_response(self, response, prompt):
        """
        display the test log.
        """
        response = re.sub("PT200\r\n\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return True, response

    def _parse_factory_set_response(self, response, prompt):
        """
        Display factory set.
        """
        response = re.sub("CR1\r\n\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return True, response

    def _parse_user_set_response(self, response, prompt):
        """
        display user set.
        """
        response = re.sub("CR0\r\n\r\n", "", response)
        response = re.sub("\r\n>", "", response)
        return True, response

    def _parse_restore_factory_params_response(self):
        """
        """