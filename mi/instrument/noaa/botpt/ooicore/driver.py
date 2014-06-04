"""
@package mi.instrument.noaa.ooicore.driver
@file marine-integrations/mi/instrument/noaa/ooicore/driver.py
@author Pete Cable
@brief BOTPT
Release notes:
"""

import re
import time
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility, ParameterDictType
import ntplib
from mi.core.common import BaseEnum, Units, Prefixes
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_protocol import DEFAULT_CMD_TIMEOUT
from mi.core.instrument.instrument_driver import DriverEvent, SingleConnectionInstrumentDriver, DriverParameter
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.exceptions import NotImplementedException, InstrumentParameterException, InstrumentProtocolException
from mi.core.exceptions import SampleException
from mi.core.instrument.driver_dict import DriverDictKey
import mi.instrument.noaa.botpt.ooicore.particles as particles
import mi.core.log

__author__ = 'Pete Cable'
__license__ = 'Apache 2.0'

log = mi.core.log.get_logger()
META_LOGGER = mi.core.log.get_logging_metaclass('debug')


###
#    Driver Constant Definitions
###

NEWLINE = '\n'

LILY_STRING = 'LILY,'
NANO_STRING = 'NANO,'
IRIS_STRING = 'IRIS,'
HEAT_STRING = 'HEAT,'
SYST_STRING = 'SYST,'

LILY_COMMAND = '*9900XY'
IRIS_COMMAND = LILY_COMMAND
NANO_COMMAND = '*0100'

NANO_RATE_RESPONSE = '*0001TH'


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
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    DISCOVER = DriverEvent.DISCOVER
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    START_DIRECT = DriverEvent.START_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    START_LEVELING = 'PROTOCOL_EVENT_START_LEVELING'
    STOP_LEVELING = 'PROTOCOL_EVENT_STOP_LEVELING'


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    AUTO_RELEVEL = "auto_relevel"  # Auto-relevel mode
    XTILT_TRIGGER = "xtilt_relevel_trigger"
    YTILT_TRIGGER = "ytilt_relevel_trigger"
    LEVELING_TIMEOUT = "relevel_timeout"
    LEVELING_FAILED = "leveling_failed"
    OUTPUT_RATE = 'output_rate_hz'
    SYNC_INTERVAL = 'time_sync_interval'
    HEAT_DURATION = "heat_duration"


class InstrumentCommand(BaseEnum):
    LILY_ON = LILY_STRING + LILY_COMMAND + 'C2'  # turns on continuous data
    LILY_OFF = LILY_STRING + LILY_COMMAND + 'C-OFF'  # turns off continuous data
    LILY_DUMP1 = LILY_STRING + LILY_COMMAND + 'DUMP_SETTINGS'  # outputs current settings
    LILY_DUMP2 = LILY_STRING + LILY_COMMAND + 'DUMP2'  # outputs current extended settings
    LILY_START_LEVELING = LILY_STRING + LILY_COMMAND + '-LEVEL,1'  # starts leveling
    LILY_STOP_LEVELING = LILY_STRING + LILY_COMMAND + '-LEVEL,0'  # stops leveling
    NANO_ON = NANO_STRING + NANO_COMMAND + 'E4'  # turns on continuous data
    NANO_OFF = NANO_STRING + NANO_COMMAND + 'E3'  # turns off continuous data
    NANO_DUMP1 = NANO_STRING + NANO_COMMAND + 'IF'  # outputs current settings
    NANO_SET_TIME = NANO_STRING + 'TS'  # requests the SBC to update the NANO time
    NANO_SET_RATE = NANO_STRING + '*0100EW*0100TH='  # sets the sample rate in Hz
    IRIS_ON = IRIS_STRING + IRIS_COMMAND + 'C2'  # turns on continuous data
    IRIS_OFF = IRIS_STRING + IRIS_COMMAND + 'C-OFF'  # turns off continuous data
    IRIS_DUMP1 = IRIS_STRING + IRIS_COMMAND + '-DUMP_SETTINGS'  # outputs current settings
    IRIS_DUMP2 = IRIS_STRING + IRIS_COMMAND + '-DUMP2'  # outputs current extended settings
    HEAT = HEAT_STRING  # turns the heater on; HEAT,<number of hours>
    SYST_DUMP1 = SYST_STRING + '1'


class Response(BaseEnum):
    LILY_ON = LILY_COMMAND + 'C2'
    LILY_OFF = LILY_COMMAND + 'C-OFF'
    IRIS_ON = IRIS_COMMAND + 'C2'
    IRIS_OFF = IRIS_COMMAND + 'C-OFF'


class DataParticleType(BaseEnum):
    NANO_SAMPLE = 'botpt_nano_sample'
    IRIS_SAMPLE = 'botpt_iris_sample'
    LILY_SAMPLE = 'botpt_lily_sample'
    HEAT_SAMPLE = 'botpt_heat_sample'
    BOTPT_STATUS = 'botpt_status'


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
    # noinspection PyMethodMayBeStatic
    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(BaseEnum, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

# noinspection PyUnusedLocal,PyMethodMayBeStatic
class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """
    __metaclass__ = META_LOGGER
    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = ThreadSafeFSM(ProtocolState, ProtocolEvent,
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        handlers = {
            ProtocolState.UNKNOWN: [
                (ProtocolEvent.ENTER, self._handler_unknown_enter),
                (ProtocolEvent.EXIT, self._handler_unknown_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
            ],
            ProtocolState.AUTOSAMPLE: [
                (ProtocolEvent.ENTER, self._handler_autosample_enter),
                (ProtocolEvent.EXIT, self._handler_autosample_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_acquire_status),
                (ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample),
                # (ProtocolEvent.START_LEVELING, self._handler_start_leveling),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_command_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_acquire_status),
                (ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample),
                # (ProtocolEvent.START_LEVELING, self._handler_start_leveling),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_direct_access_exit),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
            ],
            # ProtocolState.COMMAND_LEVELING: [
            #     (ProtocolEvent.ENTER, self._handler_leveling_enter),
            #     (ProtocolEvent.EXIT, self._handler_leveling_exit),
            #     (ProtocolEvent.GET, self._handler_command_get),
            #     (ProtocolEvent.SET, self._handler_command_set),
            #     (ProtocolEvent.STOP_LEVELING, self._handler_stop_leveling),
            #     (ProtocolEvent.LEVELING_TIMEOUT, self._handler_leveling_timeout),
            # ],
            # ProtocolState.AUTOSAMPLE_LEVELING: [
            #     (ProtocolEvent.ENTER, self._handler_leveling_enter),
            #     (ProtocolEvent.EXIT, self._handler_leveling_exit),
            #     (ProtocolEvent.GET, self._handler_command_get),
            #     (ProtocolEvent.SET, self._handler_command_set),
            #     (ProtocolEvent.STOP_LEVELING, self._handler_stop_leveling),
            #     (ProtocolEvent.LEVELING_TIMEOUT, self._handler_leveling_timeout),
            # ]
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        # self._build_command_dict()

        # Add build handlers for device commands.
        for command in InstrumentCommand.list():
            self._add_build_handler(command, self._build_simple_command)

        # # Add response handlers for device commands.
        for command in InstrumentCommand.list():
            self._add_response_handler(command, self._generic_response_handler)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

        self.initialize_scheduler()

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that filters LILY chunks
        """
        matchers = []
        return_list = []

        matchers.append(particles.HEATDataParticle.regex_compiled())
        matchers.append(particles.IRISDataParticle.regex_compiled())
        matchers.append(particles.NANODataParticle.regex_compiled())
        matchers.append(particles.LILYDataParticle.regex_compiled())
        matchers.append(particles.LILYLevelingParticle.regex_compiled())


        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _got_chunk(self, chunk, ts):
        possible_particles = [
            (particles.LILYDataParticle, None), #self._check_for_autolevel),
            (particles.LILYLevelingParticle, None), # self._check_completed_leveling),
            (particles.HEATDataParticle, None),
            (particles.IRISDataParticle, None),
            (particles.NANODataParticle, None),
        ]

        for particle_type, func in possible_particles:
            sample = self._extract_sample(particle_type, particle_type.regex_compiled(), chunk, ts)
            if sample:
                if func:
                    func(sample)
                return sample

        raise InstrumentProtocolException('unhandled chunk received by _got_chunk: [%r]', chunk)

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        my_regex = 'Not used'
        ro, rw = ParameterDictVisibility.READ_ONLY, ParameterDictVisibility.READ_WRITE
        _bool, _float, _int = ParameterDictType.BOOL, ParameterDictType.FLOAT, ParameterDictType.INT

        parameters = {
            Parameter.AUTO_RELEVEL: {
                'type': _bool,
                'display_name': 'Automatic Releveling Enabled',
                'visibility': rw,
            },
            Parameter.XTILT_TRIGGER: {
                'type': _float,
                'display_name': 'X-tilt Releveling Trigger',
                'units': Prefixes.MICRO + Units.RADIAN,
                'visibility': rw,
            },
            Parameter.YTILT_TRIGGER: {
                'type': _float,
                'display_name': 'Y-tilt Releveling Trigger',
                'visibility': rw,
            },
            Parameter.LEVELING_TIMEOUT: {
                'type': _int,
                'display_name': 'LILY Leveling Timeout',
                'units': Prefixes.MICRO + Units.RADIAN,
                'visibility': rw,
            },
            Parameter.LEVELING_FAILED: {
                'type': _bool,
                'display_name': 'LILY Leveling Failed',
                'visibility': ro,
            },
            Parameter.HEAT_DURATION: {
                'type': _int,
                'display_name': 'Heater Run Time Duration',
                'units': Units.SECOND,
                'visibility': rw,
            },
            Parameter.OUTPUT_RATE: {
                'type': _int,
                'display_name': 'NANO Output Rate',
                'units': Units.HERTZ,
                'visibility': rw,
            },
            Parameter.SYNC_INTERVAL: {
                'type': _int,
                'display_name': 'NANO Time Sync Interval',
                'units': Units.SECOND,
                'visibility': rw,
            },
        }
        for param in parameters:
            self._param_dict.add(param, my_regex, None, None, **parameters[param])

        self._param_dict.set_value(Parameter.LEVELING_FAILED, False)

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, False)

    def _handler_command_generic(self, command, next_state, next_agent_state,
                                 timeout=DEFAULT_CMD_TIMEOUT, expected_prompt=None, response_regex=None):
        """
        Generic method to command the instrument
        """
        if expected_prompt is None and response_regex is None:
            result = self._do_cmd_no_resp(command)
        else:
            result = self._do_cmd_resp(command, expected_prompt=expected_prompt,
                                       response_regex=response_regex, timeout=timeout)

        return next_state, (next_agent_state, result)

    def _verify_set_values(self, params):
        """
        Verify supplied values are in range, if applicable
        """

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters
        """
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        self._verify_set_values(params)
        self._verify_not_readonly(*args, **kwargs)

        old_config = self._param_dict.get_config()
        for key, value in params.items():
            self._param_dict.set_value(key, value)
        new_config = self._param_dict.get_config()

        if not old_config == new_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _update_params(self, *args, **kwargs):
        pass

    def _wakeup(self, timeout, delay=1):
        """
        Overriding _wakeup; does not apply to this instrument
        """

    def _stop_autosample(self):
        self._do_cmd_no_resp(InstrumentCommand.NANO_OFF)
        self._do_cmd_resp(InstrumentCommand.LILY_OFF, expected_prompt=Response.LILY_OFF)
        self._do_cmd_resp(InstrumentCommand.IRIS_OFF, expected_prompt=Response.IRIS_OFF)

    def _generic_response_handler(self, *args, **kwargs):
        pass

    def _handler_acquire_status(self, *args, **kwargs):
        pass

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_discover(self, *args, **kwargs):
        return ProtocolState.COMMAND, ResourceAgentState.IDLE

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        self._init_params()
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit command state.
        """

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        self._stop_autosample()
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        """
        self._init_params()
        self._stop_autosample()
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        return self._handler_get(*args, **kwargs)

    def _handler_command_set(self, *args, **kwargs):
        """
        Perform a set command.
        @param args[0] parameter : value dict.
        @retval (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set parameters not ALL and
        not a dict, or if parameter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
        next_state = None
        result = None
        startup = False

        if len(args) < 1:
            raise InstrumentParameterException('Set command requires a parameter dict.')
        params = args[0]
        if len(args) > 1:
            startup = args[1]

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')
        if not isinstance(startup, bool):
            raise InstrumentParameterException('Startup not a bool.')

        self._set_params(params, startup)
        return next_state, result

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """

    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        return ProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    def _handler_command_start_autosample(self):
        self._do_cmd_resp(InstrumentCommand.LILY_ON, expected_prompt=Response.LILY_ON)
        self._do_cmd_no_resp(InstrumentCommand.NANO_ON)
        self._do_cmd_resp(InstrumentCommand.IRIS_ON, expected_prompt=Response.IRIS_ON)
        return ProtocolState.AUTOSAMPLE, (ResourceAgentState.STREAMING, None)

    ########################################################################
    # Direct access handlers.
    ########################################################################

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

    def _handler_direct_access_execute_direct(self, data):
        """
        """
        self._do_cmd_direct(data )
        self._sent_cmds.append(data)
        return None, (None, None)

    def _handler_direct_access_stop_direct(self):
        """
        """
        result = None

        next_state, next_agent_state = self._handler_unknown_discover()
        if next_state == DriverProtocolState.COMMAND:
            next_agent_state = ResourceAgentState.COMMAND

        return next_state, (next_agent_state, result)