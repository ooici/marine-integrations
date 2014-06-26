"""
@package mi.instrument.harvard.massp.turbo.driver
@file marine-integrations/mi/instrument/harvard/massp/turbo/driver.py
@author Peter Cable
@brief Driver for the turbo
Release notes:

Turbo driver for the MASSP in-situ mass spectrometer
"""

import re
import time

import mi.core.exceptions as exceptions
from mi.core.driver_scheduler import TriggerType
from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.log import get_logger
from mi.core.log import get_logging_metaclass
from mi.core.common import BaseEnum, Units, Prefixes
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.chunker import StringChunker
from mi.instrument.harvard.massp.common import MASSP_STATE_ERROR, MASSP_CLEAR_ERROR


__author__ = 'Peter Cable'
__license__ = 'Apache 2.0'

log = get_logger()

###
#    Driver Constant Definitions
###

NEWLINE = '\r'
TIMEOUT = 1
ADDRESS = 1
QUERY = '=?'
TRUE = '111111'
FALSE = '000000'
TURBO_RESPONSE = re.compile('^(\d*)\r')
MAX_RETRIES = 5
CURRENT_STABILIZE_RETRIES = 5
META_LOGGER = get_logging_metaclass()


class ScheduledJob(BaseEnum):
    """
    All scheduled jobs for this driver
    """
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS


class CommandType(BaseEnum):
    """
    Command types for the turbo. Used by build_command.
    """
    QUERY = 0
    SET = 10


class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW
    TURBO_STATUS = 'massp_turbo_status'


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    SPINNING_UP = 'PROTOCOL_STATE_SPINNING_UP'
    AT_SPEED = 'PROTOCOL_STATE_AT_SPEED'
    SPINNING_DOWN = 'PROTOCOL_STATE_SPINNING_DOWN'
    ERROR = MASSP_STATE_ERROR


class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    START_TURBO = 'PROTOCOL_EVENT_START_TURBO'
    STOP_TURBO = 'PROTOCOL_EVENT_STOP_TURBO'
    AT_SPEED = 'PROTOCOL_EVENT_AT_SPEED'
    ERROR = 'PROTOCOL_EVENT_ERROR'
    CLEAR = MASSP_CLEAR_ERROR
    STOPPED = 'PROTOCOL_EVENT_STOPPED'


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    ACQUIRE_STATUS is exposed to facilitate testing, but is not expected to be received
    from outside the driver during normal operations.  Instead it is run at a scheduled
    interval, once every Parameter.UPDATE_INTERVAL seconds.
    """
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
    START_TURBO = ProtocolEvent.START_TURBO
    STOP_TURBO = ProtocolEvent.STOP_TURBO
    CLEAR = ProtocolEvent.CLEAR


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    UPDATE_INTERVAL = 'turbo_status_update_interval'
    MAX_TEMP_BEARING = 'turbo_max_temp_bearing'
    MAX_TEMP_MOTOR = 'turbo_max_temp_motor'
    MAX_DRIVE_CURRENT = 'turbo_max_drive_current'
    MIN_SPEED = 'turbo_min_speed'
    TARGET_SPEED = 'turbo_target_speed'
    ERROR_REASON = 'turbo_error_reason'

    @classmethod
    def reverse_dict(cls):
        return dict((v, k) for k, v in cls.dict().iteritems())


class ParameterConstraints(BaseEnum):
    UPDATE_INTERVAL = (int, 5, 60)
    MAX_DRIVE_CURRENT = (int, 100, 200)
    MAX_TEMP_MOTOR = (int, 5, 100)
    MAX_TEMP_BEARING = (int, 5, 100)
    MIN_SPEED = (int, 70000, 90000)
    TARGET_SPEED = (int, 70000, 90000)


class Prompt(BaseEnum):
    """
    Device i/o prompts..
    None for the turbo.
    """


class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    # CONTROL
    ERROR_ACK = 9
    PUMP_STATION = 10
    MOTOR_PUMP = 23
    SPEED_SET = 26
    # STATUS
    ERROR_CODE = 303
    EXCESS_TEMP_EDU = 304
    EXCESS_TEMP_PUMP = 305
    SPEED_ATTAINED = 306
    PUMP_ACCELERATES = 307
    DRIVE_CURRENT = 310
    DRIVE_VOLTAGE = 313
    TEMP_ELECTRONIC = 326
    ACCEL = 336
    TEMP_BEARING = 342
    TEMP_MOTOR = 346
    ROTATION_SPEED_SET = 397
    ROTATION_SPEED_ACTUAL = 398
    # SETTINGS
    SET_RUNUP_TIME = 700
    SET_SPEED_VALUE = 707
    SET_POWER_VALUE = 708


###############################################################################
# Data Particles
###############################################################################


class TurboStatusParticleKey(BaseEnum):
    """
    Keys for the turbo status particle
    """
    DRIVE_CURRENT = 'massp_turbo_drive_current'
    DRIVE_VOLTAGE = 'massp_turbo_drive_voltage'
    TEMP_BEARING = 'massp_turbo_bearing_temperature'
    TEMP_MOTOR = 'massp_turbo_motor_temperature'
    ROTATION_SPEED = 'massp_turbo_rotation_speed'


# noinspection PyMethodMayBeStatic,PyProtectedMember
class TurboStatusParticle(DataParticle):
    """
    Example data:
    0011031006000000012
    0011031306002346030
    0011034206000028027
    0011034606000029032
    0011039806000000028

    These are the responses from 5 commands sent to the turbopump during acquire_status.
    """
    __metaclass__ = META_LOGGER
    _data_particle_type = DataParticleType.TURBO_STATUS

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        regex_list = []
        for command in ['DRIVE_CURRENT', 'DRIVE_VOLTAGE', 'TEMP_BEARING', 'TEMP_MOTOR', 'ROTATION_SPEED_ACTUAL']:
            regex_list.append(r'(?P<%s>00110%03d06\d{9})\r' % (command, getattr(InstrumentCommand, command)))
        return ''.join(regex_list)

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(TurboStatusParticle.regex())

    def _extract(self, data):
        """
        Extract the data portion from the response
        """
        checksum = data[-3:]
        calc_checksum = Protocol._checksum(data[:-3])
        if checksum != calc_checksum:
            raise exceptions.InstrumentDataException('Invalid checksum on %s, calculated %s' % (data, calc_checksum))
        return int(data[-9:-3])

    def _build_parsed_values(self):
        """
        Run our regex against the input, format the results and pack for publishing.
        """
        tspk = TurboStatusParticleKey
        try:
            match = self.regex_compiled().match(self.raw_data)
            result = [
                self._encode_value(tspk.DRIVE_CURRENT, self._extract(match.group('DRIVE_CURRENT')), int),
                self._encode_value(tspk.DRIVE_VOLTAGE, self._extract(match.group('DRIVE_VOLTAGE')), int),
                self._encode_value(tspk.TEMP_BEARING, self._extract(match.group('TEMP_BEARING')), int),
                self._encode_value(tspk.TEMP_MOTOR, self._extract(match.group('TEMP_MOTOR')), int),
                self._encode_value(tspk.ROTATION_SPEED, self._extract(match.group('ROTATION_SPEED_ACTUAL')), int),
            ]
        except ValueError, e:
            raise exceptions.SampleException('Corrupt turbo status received (%s)', e)
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
    __metaclass__ = META_LOGGER

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

# noinspection PyMethodMayBeStatic,PyUnusedLocal
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
        self._protocol_fsm = ThreadSafeFSM(ProtocolState, ProtocolEvent, ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        handlers = {
            ProtocolState.UNKNOWN: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.START_TURBO, self._handler_command_start_turbo),
            ],
            ProtocolState.SPINNING_UP: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_acquire_status),
                (ProtocolEvent.STOP_TURBO, self._handler_stop_turbo),
                (ProtocolEvent.AT_SPEED, self._handler_spinning_up_at_speed),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.AT_SPEED: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STOP_TURBO, self._handler_stop_turbo),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_acquire_status),
                (ProtocolEvent.ERROR, self._handler_error),
            ],
            ProtocolState.ERROR: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_acquire_status),
                (ProtocolEvent.STOP_TURBO, self._handler_stop_turbo),
                (ProtocolEvent.CLEAR, self._handler_clear),
                (ProtocolEvent.GET, self._handler_command_get),
            ],
            ProtocolState.SPINNING_DOWN: [
                (ProtocolEvent.ENTER, self._handler_generic_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.ACQUIRE_STATUS, self._handler_acquire_status),
                (ProtocolEvent.STOPPED, self._handler_spinning_down_stopped),
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_generic_exit),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
            ],
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        # Add build and response handlers for device commands.
        for command in InstrumentCommand.list():
            self._add_build_handler(command, self._generic_build_handler)
            self._add_response_handler(command, self._generic_response_handler)

        # Start state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)
        self._max_current_count = 0
        self.initialize_scheduler()

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        @param raw_data: data to be searched
        @return: list of (start,stop) indexes of matches
        """
        return [(m.start(), m.end()) for m in TurboStatusParticle.regex_compiled().finditer(raw_data)]

    def _build_param_dict(self):
        """
        All turbo parameters have the same signature, add them in a loop...
        """
        parameters = {
            Parameter.UPDATE_INTERVAL: {
                'display_name': 'Acquire Status Interval',
                'description': 'Interval between automatic acquire status calls',
                'units': Units.SECOND,
                'type': ParameterDictType.INT,
                'startup_param': True,
            },
            Parameter.MAX_DRIVE_CURRENT: {
                'display_name': 'Maximum Allowable Drive Current',
                'description': 'Maximum allowable drive current (at speed)',
                'units': Prefixes.CENTI + Units.AMPERE,
                'type': ParameterDictType.INT,
                'startup_param': True,
            },
            Parameter.MAX_TEMP_MOTOR: {
                'display_name': 'Maximum Allowable Motor Temperature',
                'description': 'Maximum allowable motor temperature',
                'units': Units.DEGREE_CELSIUS,
                'type': ParameterDictType.INT,
                'startup_param': True,
            },
            Parameter.MAX_TEMP_BEARING: {
                'display_name': 'Maximum Allowable Bearing Temperature',
                'description': 'Maximum allowable bearing temperature',
                'units': Units.DEGREE_CELSIUS,
                'type': ParameterDictType.INT,
                'startup_param': True,
            },
            Parameter.MIN_SPEED: {
                'display_name': 'Minimum Allowable Turbo Speed',
                'description': 'Minimum allowable turbo speed before RGA is shutdown',
                'units': Units.REVOLUTION_PER_MINUTE,
                'type': ParameterDictType.INT,
                'startup_param': True,
            },
            Parameter.TARGET_SPEED: {
                'display_name': 'Target Turbo Speed',
                'description': 'Target turbo speed before RGA is initialized',
                'units': Units.REVOLUTION_PER_MINUTE,
                'type': ParameterDictType.INT,
                'startup_param': True,
            },
            Parameter.ERROR_REASON: {
                'display_name': 'Reason for Turbo Error Condition',
                'description': 'Reason for turbo error condition',
                'visibility': ParameterDictVisibility.READ_ONLY,
                'type': ParameterDictType.STRING,
            }
        }

        reverse_param = Parameter.reverse_dict()
        constraints = ParameterConstraints.dict()

        for name in parameters:
            kwargs = parameters[name]
            if name in constraints:
                _type, minimum, maximum = constraints[name]
                kwargs['val_description'] = '%s value from %d - %d' % (_type, minimum, maximum)
            self._param_dict.add(name, '', None, None, **kwargs)

    def _build_command_dict(self):
        """
        Populate the command dictionary with commands.
        """
        self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name="Acquire status")
        self._cmd_dict.add(Capability.START_TURBO, display_name="Start turbo")
        self._cmd_dict.add(Capability.STOP_TURBO, display_name="Stop turbo")
        self._cmd_dict.add(Capability.CLEAR, display_name="Clear error state")

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, False)

    def _got_chunk(self, chunk, ts):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and regexes.
        @param chunk: data to be processed
        @param ts: timestamp
        """
        self._extract_sample(TurboStatusParticle, TurboStatusParticle.regex_compiled(), chunk, ts)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        @param events: events to be filtered
        @return: list of events that are in Capability
        """
        return [x for x in events if Capability.has(x)]

    @staticmethod
    def _checksum(s):
        """
        Calculate the turbopump checksum for the given string.
        @param s: string to be checked
        @return: checksum string
        """
        return '%03d' % (sum([ord(x) for x in s]) % 256)

    def _build_turbo_command(self, address, c_type, c, data):
        """
        Build a command for the turbopump
        @param address: target address
        @param c_type: command type (QUERY/SET)
        @param c: command
        @param data: command_data
        @return: command string
        """
        command = '%03d%02d%03d%02d%s' % (address, c_type, c, len(data), data)
        checksum = self._checksum(command)
        return command + checksum

    def _generic_build_handler(self, command, *args, **kwargs):
        """
        Determine if this is a query or set action based on the
        input args.  Dispatch the builder with the appropriate arguments.
        @param command: command to be sent
        @param args: arglist which may contain a value
        @return: command string
        """
        if len(args) == 1:
            # this is a set action
            value = args[0]
            return self._build_turbo_command(ADDRESS, CommandType.SET, command, value) + NEWLINE
        # this is a query
        return self._build_turbo_command(ADDRESS, CommandType.QUERY, command, QUERY) + NEWLINE

    def _generic_response_handler(self, resp, prompt):
        """
        Parse the response from the turbopump.
        @param resp: response
        @param prompt: unused, require to match signature
        @returns: integer value extracted from response
        @throws InstrumentDataException
        """
        my_checksum = self._checksum(resp[:-3])
        if resp[-3:] != my_checksum:
            err_str = 'bad checksum: %r calculated: %r' % (resp, my_checksum)
            raise exceptions.InstrumentDataException(err_str)
        command = int(resp[5:8])
        data_length = int(resp[8:10])
        data = resp[10:-3]
        log.trace('command: %s data: %s', command, data)
        if len(data) != data_length:
            raise exceptions.InstrumentDataException('invalid data length: %r' % resp)
        if command not in InstrumentCommand.list():
            raise exceptions.InstrumentDataException('command not found: %r' % resp)
        return int(data)

    def _wakeup(self, timeout, delay=1):
        """
        Not valid for this instrument
        """

    def _build_scheduler(self):
        """
        Build a scheduler for periodic status updates
        """
        job_name = ScheduledJob.ACQUIRE_STATUS
        config = {
            DriverConfigKey.SCHEDULER: {
                job_name: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.SECONDS: self._param_dict.get(Parameter.UPDATE_INTERVAL)
                    },
                }
            }
        }

        self.set_init_params(config)
        self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS, ProtocolEvent.ACQUIRE_STATUS)

    def _update_params(self, *args, **kwargs):
        """
        Parameters are NOT set in the instrument by this method, as all parameters are driver only.
        """

    def _set_params(self, *args, **kwargs):
        """
        Set parameters, raise a CONFIG_CHANGE event if necessary.
        @throws InstrumentParameterException
        """
        self._verify_not_readonly(*args, **kwargs)
        params_to_set = args[0]
        old_config = self._param_dict.get_all()

        # check if in range
        constraints = ParameterConstraints.dict()
        parameters = Parameter.reverse_dict()

        # step through the list of parameters
        for key, val in params_to_set.iteritems():
            # if constraint exists, verify we have not violated it
            constraint_key = parameters.get(key)
            if constraint_key in constraints:
                var_type, minimum, maximum = constraints[constraint_key]
                try:
                    value = var_type(val)
                except ValueError:
                    raise exceptions.InstrumentParameterException(
                        'Unable to verify type - parameter: %s value: %s' % (key, val))
                if val < minimum or val > maximum:
                    raise exceptions.InstrumentParameterException(
                        'Value out of range - parameter: %s value: %s min: %s max: %s' %
                        (key, val, minimum, maximum))

        # all constraints met or no constraints exist, set the values
        for key, val in params_to_set.iteritems():
            if key in old_config:
                self._param_dict.set_value(key, val)
            else:
                raise exceptions.InstrumentParameterException(
                    'Attempted to set unknown parameter: %s value: %s' % (key, val))
        new_config = self._param_dict.get_all()

        # If we changed anything, raise a CONFIG_CHANGE event
        if old_config != new_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _send_command_with_retry(self, command, value=None, sleep_time=1, max_retries=MAX_RETRIES):
        """
        Attempt to send a command up to max_retries times.  Protocol state will move to ERROR if we fail to
        receive a response after max_retries attempts.
        @throws InstrumentTimeoutException
        """
        for attempt in xrange(1, max_retries + 1):
            try:
                if value is None:
                    result = self._do_cmd_resp(command, response_regex=TURBO_RESPONSE, timeout=TIMEOUT)
                else:
                    result = self._do_cmd_resp(command, value, response_regex=TURBO_RESPONSE, timeout=TIMEOUT)
                return result
            except exceptions.InstrumentTimeoutException:
                log.error('Error sending command: %s, attempt %d', command, attempt)
                time.sleep(sleep_time)

        # set the error reason
        self._param_dict.set_value(Parameter.ERROR_REASON, 'Unable to command the turbo')
        self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

        self._async_raise_fsm_event(ProtocolEvent.ERROR)
        raise exceptions.InstrumentTimeoutException('Failed to command the turbo: %s' % command)

    ########################################################################
    # Generic handlers.
    ########################################################################

    def _handler_generic_enter(self, *args, **kwargs):
        """
        Generic enter handler when no specific action is needed.
        """
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_generic_exit(self, *args, **kwargs):
        """
        Generic exit handler when no specific action is needed.
        """

    def _handler_acquire_status(self, *args, **kwargs):
        """
        Query the instrument for the following status items:
            drive current
            drive voltage
            bearing temp
            motor temp
            rotation speed

        Verify no values exceed the limits specified in the parameter dictionary.
        @returns: next_state, (next_agent_state, result)
        @throws InstrumentStateException
        """
        responses = {}

        # query the turbo for the speed/temp/current values
        for command in [InstrumentCommand.DRIVE_CURRENT, InstrumentCommand.DRIVE_VOLTAGE,
                        InstrumentCommand.TEMP_BEARING, InstrumentCommand.TEMP_MOTOR,
                        InstrumentCommand.ROTATION_SPEED_ACTUAL]:
            responses[command] = self._send_command_with_retry(command)

        # check the current driver state
        current_state = self.get_current_state()
        error = None

        # Check for over temperature conditions
        if responses[InstrumentCommand.TEMP_MOTOR] > self._param_dict.get(Parameter.MAX_TEMP_MOTOR) or \
                responses[InstrumentCommand.TEMP_BEARING] > self._param_dict.get(Parameter.MAX_TEMP_BEARING):
            error = 'Over temp error - Motor: %d Bearing: %d' % (responses[InstrumentCommand.TEMP_MOTOR],
                                                                 responses[InstrumentCommand.TEMP_BEARING])

        # Check if we were up to speed but have dipped below MIN_SPEED
        elif current_state == ProtocolState.AT_SPEED:
            if responses[InstrumentCommand.ROTATION_SPEED_ACTUAL] < self._param_dict.get(Parameter.MIN_SPEED):
                error = 'Fell below min speed: %d' % responses[InstrumentCommand.ROTATION_SPEED_ACTUAL]

            # or if we're up to speed and we have exceeded MAX_DRIVE_CURRENT more than 3 subsequent intervals
            if responses[InstrumentCommand.DRIVE_CURRENT] > self._param_dict.get(Parameter.MAX_DRIVE_CURRENT):
                self._max_current_count += 1
                if self._max_current_count > CURRENT_STABILIZE_RETRIES:
                    error = 'Turbo current draw to high: %d' % responses[InstrumentCommand.DRIVE_CURRENT]
            else:
                self._max_current_count = 0

        if error:
            self._param_dict.set_value(Parameter.ERROR_REASON, error)
            self._async_raise_fsm_event(ProtocolEvent.ERROR)
            self._driver_event(DriverAsyncEvent.ERROR, error)

        # now check if up to speed when spinning up
        elif current_state == ProtocolState.SPINNING_UP:
            if responses[InstrumentCommand.ROTATION_SPEED_ACTUAL] >= self._param_dict.get(Parameter.TARGET_SPEED):
                self._async_raise_fsm_event(ProtocolEvent.AT_SPEED)

        # or maybe we've stopped while spinning down (we'll consider < MIN_SPEED as stopped...)
        elif current_state == ProtocolState.SPINNING_DOWN:
            if responses[InstrumentCommand.ROTATION_SPEED_ACTUAL] <= self._param_dict.get(Parameter.MIN_SPEED):
                self._async_raise_fsm_event(ProtocolEvent.STOPPED)

        return None, (None, responses)

    def _handler_stop_turbo(self):
        """
        Stop the turbo
        @returns: next_state, (next_agent_state, result)
        """
        for command in [InstrumentCommand.PUMP_STATION, InstrumentCommand.MOTOR_PUMP]:
            self._send_command_with_retry(command, value=FALSE)

        return ProtocolState.SPINNING_DOWN, (ResourceAgentState.BUSY, None)

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state.  This instrument always discovers to COMMAND
        @returns: next_state, next_agent_state
        """
        return ProtocolState.COMMAND, ResourceAgentState.IDLE

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        """
        self._init_params()

        # delete the scheduled acquire status job, if it exists.
        # This portion of the MASSP is powered OFF the majority of the time
        # so acquire_status should not be running
        try:
            self._remove_scheduler(ScheduledJob.ACQUIRE_STATUS)
        except KeyError:
            pass

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        @returns: next_state, result
        """
        return self._handler_get(*args, **kwargs)

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        @returns: next_state, result
        """
        next_state = None
        result = None
        self._set_params(*args, **kwargs)

        return next_state, result

    def _handler_command_start_direct(self):
        """
        Start direct access
        @returns: next_state, (next_agent_state, result)
        """
        return ProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    def _handler_command_start_turbo(self):
        """
        Start the turbo, periodic status scheduler
        @returns: next_state, (next_agent_state, result)
        """
        for command in [InstrumentCommand.PUMP_STATION, InstrumentCommand.MOTOR_PUMP]:
            self._send_command_with_retry(command, value=TRUE)
        # start the acquire_status scheduler
        self._build_scheduler()
        return ProtocolState.SPINNING_UP, (ResourceAgentState.BUSY, None)

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

    def _handler_direct_access_execute_direct(self, data):
        """
        Forward a direct access command to the instrument
        @returns: next_state, (next_agent_state, result)
        """
        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return None, (None, None)

    def _handler_direct_access_stop_direct(self):
        """
        Stop direct access, return to COMMAND
        @returns: next_state, (next_agent_state, result)
        """
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Spinning up/down handlers.
    ########################################################################

    def _handler_spinning_up_at_speed(self):
        """
        Instrument has reached operating speed, transition states.
        @returns: next_state, next_agent_state
        """
        return ProtocolState.AT_SPEED, ResourceAgentState.BUSY

    def _handler_spinning_down_stopped(self):
        """
        Instrument has spun down, transition states.
        @returns: next_state, next_agent_state
        """
        self._async_agent_state_change(ResourceAgentState.COMMAND)
        return ProtocolState.COMMAND, ResourceAgentState.COMMAND

    ########################################################################
    # Error handlers.
    ########################################################################

    def _handler_error(self, *args, **kwargs):
        """
        Error detected, go to the ERROR state.
        @returns: next_state, (next_agent_state, result)
        """
        return ProtocolState.ERROR, (ResourceAgentState.COMMAND, None)

    def _handler_clear(self, *args, **kwargs):
        """
        User requests error state be cleared, go to COMMAND.
        @returns: next_state, (next_agent_state, result)
        """
        self._param_dict.set_value(Parameter.ERROR_REASON, '')
        self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)
