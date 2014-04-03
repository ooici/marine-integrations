"""
@package mi.instrument.mclane.ras.ooicore.driver
@file marine-integrations/mi/instrument/mclane/ras/ooicore/driver.py
@author Dan Mergens
@brief Driver for the PPSDN
Release notes:

initial version
"""
import datetime

__author__ = 'Dan Mergens'
__license__ = 'Apache 2.0'

import re
import time

from mi.core.log import get_logger

log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, \
    InstrumentProtocolException, \
    InstrumentTimeoutException

from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol, RE_PATTERN
from mi.core.instrument.instrument_protocol import DEFAULT_CMD_TIMEOUT
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverConnectionState

from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState

from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType

from mi.core.instrument.driver_dict import DriverDictKey

from mi.core.instrument.protocol_param_dict import ProtocolParameterDict, \
    ParameterDictType, \
    ParameterDictVisibility


NEWLINE = '\r\n'
CONTROL_C = '\x03'
NUM_PORTS = 24  # number of collection bags

# default timeout.
INTER_CHARACTER_DELAY = .2  # works
# INTER_CHARACTER_DELAY = .02 - too fast
# INTER_CHARACTER_DELAY = .04

####
#    Driver Constant Definitions
####


class ScheduledJob(BaseEnum):
    CLOCK_SYNC = 'clock_sync'


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    FLUSH = 'DRIVER_STATE_FLUSH'
    FILL = 'DRIVER_STATE_FILL'
    CLEAR = 'DRIVER_STATE_CLEAR'
    RECOVERY = 'DRIVER_STATE_RECOVERY'  # for recovery after pump failure


class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    DISCOVER = DriverEvent.DISCOVER
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    FLUSH = 'DRIVER_EVENT_FLUSH'
    FILL = 'DRIVER_EVENT_FILL'
    CLEAR = 'DRIVER_EVENT_CLEAR'
    PUMP_STATUS = 'DRIVER_EVENT_PUMP_STATUS'
    INSTRUMENT_FAILURE = 'DRIVER_EVENT_INSTRUMENT_FAILURE'


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
    CLEAR = ProtocolEvent.CLEAR


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    FLUSH_VOLUME = "PPSFlush_volume"
    FLUSH_FLOWRATE = "PPSFlush_flowrate"
    FLUSH_MINFLOW = "PPSFlush_minflow"
    FILL_VOLUME = "PPSFill_volume"
    FILL_FLOWRATE = "PPSFill_flowrate"
    FILL_MINFLOW = "PPSFill_minflow"
    REVERSE_VOLUME = "PPSReverse_volume"
    REVERSE_FLOWRATE = "PPSReverse_flowrate"
    REVERSE_MINFLOW = "PPSReverse_minflow"


class Command(BaseEnum):
    """
    Instrument command strings - case insensitive
    """
    GO = NEWLINE
    CONTROL_C = CONTROL_C
    CLOCK = 'clock'  # set the clock date and time
    BATTERY = 'battery'  # display battery voltage
    HOME = 'home'  # set the port to the home port (0)
    FORWARD = 'forward'  # start forward pump operation < volume flowrate minflow [time] >
    REVERSE = 'reverse'  # reverse pump operation < volume flowrate minflow [time] >
    PORT = 'port'  # display current port or set valve to supplied position


class Prompt(BaseEnum):
    """
    Device i/o prompts.
    """
    CR_NL = '\r\n'
    PERIOD = '.'
    SUSPENDED = 'Suspended ... '
    ENTER_CTRL_C = 'Enter ^C now to wake up ...'
    COMMAND_INPUT = '>'
    UNRECOGNIZED_COMMAND = '] unrecognized command'


class Response(BaseEnum):
    """
    Expected device response strings
    """
    HOME = re.compile(r'Port: 00')
    PORT = re.compile(r'Port: (\d+)')  # e.g. Port: 01
    # e.g. 03/25/14 20:24:02 PPS ML13003-01>
    READY = re.compile(r'(\d+/\d+/\d+\s+\d+:\d+:\d+\s+)PPS (.*)>')
    # Result 00 |  75 100  25   4 |  77.2  98.5  99.1  47 031514 001813 | 29.8 1
    # Result 00 |  10 100  75  60 |  10.0  85.5 100.0   7 032814 193855 | 30.0 1
    PUMP = re.compile(r'(Status|Result).*(\d+)' + NEWLINE)


class Timeout(BaseEnum):
    # TODO - do we want to poll for status (check each second for status) or do we want to wait for the completion of
    # the entire command?
    """
    Timeouts for commands  # TODO - calculate based on flow rate & volume
    """
    HOME = 30
    PORT = 10 + 2  # average time to advance to next port is 10 seconds, any more indicates skipping of a port
    FLUSH = 103 + 5
    FILL = 2728 + 30
    CLEAR = 68 + 5
    ACQUIRE_SAMPLE = HOME + FLUSH + PORT + FILL + HOME + CLEAR
    # quick test parameter
    # ACQUIRE_SAMPLE = 600


#####
# Codes for pump termination

TerminationCodes = {
    0: 'Pumping in progress',
    1: 'Volume reached',
    2: 'Time limit reached',
    3: 'Min flow reached',
    4: 'Low battery',
    5: 'Stopped by user',
    6: 'Pump would not start',
    7: 'Sudden flow obstruction',
    8: 'Sudden obstruction with slip',
    9: 'Sudden pressure release'
}


class TerminationCodeEnum(BaseEnum):
    PUMP_IN_PROGRESS = 0
    VOLUME_REACHED = 1
    TIME_LIMIT_REACHED = 2
    MIN_FLOW_REACHED = 3
    LOW_BATTERY = 4
    STOPPED_BY_USER = 5
    PUMP_WOULD_NOT_START = 6
    SUDDEN_FLOW_OBSTRUCTION = 7
    SUDDEN_OBSTRUCTION_WITH_SLIP = 8
    SUDDEN_PRESSURE_RELEASE = 9


class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    # TODO - define which commands will be published to user
    RAW = CommonDataParticleType.RAW
    RASFL_PARSED = 'rasfl_parsed'
    PUMP_STATUS = 'rasfl_pump_status'
    VOLTAGE_STATUS = 'rasfl_battery'
    VERSION_INFO = 'rasfl_version'


###############################################################################
# Data Particles
###############################################################################

class RASFLVoltageDataParticleKey(BaseEnum):
    VOLTAGE = 'battery_voltage'


class RASFLVoltageDataParticle(DataParticle):
    _data_particle_type = DataParticleType.RASFL_PARSED

    # parse the battery return string, e.g.:
    # Battery: 29.9V [Alkaline, 18V minimum]
    @staticmethod
    def regex():
        exp = r'Battery:\s*(\d*\.*\d+)\s*'
        return exp

    @staticmethod
    def regex_compiled():
        return re.compile(RASFLVoltageDataParticle.regex(), re.DOTALL)

    def _build_parsed_values(self):
        match = self.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("RASFL_VoltageDataParticle: No regex match of parsed sample data: [%s]",
                                  self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: RASFLVoltageDataParticleKey.VOLTAGE,
             DataParticleKey.VALUE: float(match.group(1))},
        ]

        return result


# TODO - get the actual list of particles
class RASFLVersionDataParticleKey(BaseEnum):
    VERSION = 'version'
    RELEASE_DATE = 'release_date'
    PUMP_TYPE = 'pump_type'
    BAG_CAPACITY = 'bag_capacity'


# data particle for version command
class RASFLVersionDataParticle(DataParticle):
    _data_particle_type = DataParticleType.RASFL_PARSED

    @staticmethod
    def regex():
        exp = str(r'Version:\s*' + NEWLINE +
                  '\s*' + NEWLINE +
                  'McLane Research Laboratories, Inc\.\s*$' + NEWLINE +
                  'kF2 Adaptive Remote Sampler\s*$' + NEWLINE +
                  'Version (\S+) of (.*)$' + NEWLINE +
                  'Pump type:\s*(.*)$' + NEWLINE +
                  'Bag capacity:\s*(\d+)\s*')
        return exp

    @staticmethod
    def regex_compiled():
        return re.compile(RASFLVersionDataParticle.regex(), re.DOTALL)

    def _build_parsed_values(self):
        match = RASFLVersionDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("RASFL_VersionDataParticle: No regex match of parsed sample data: [%s]",
                                  self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: RASFLVersionDataParticleKey.VERSION,
             DataParticleKey.VALUE: str(match.group(1))},
            {DataParticleKey.VALUE_ID: RASFLVersionDataParticleKey.RELEASE_DATE,
             DataParticleKey.VALUE: str(match.group(2))},
            {DataParticleKey.VALUE_ID: RASFLVersionDataParticleKey.PUMP_TYPE,
             DataParticleKey.VALUE: str(match.group(3))},
            {DataParticleKey.VALUE_ID: RASFLVersionDataParticleKey.BAG_CAPACITY,
             DataParticleKey.VALUE: str(match.group(4))},
        ]

        return result


class RASFLSampleDataParticleKey(BaseEnum):
    PUMP_STATUS = 'pump_status'
    PORT = 'port'
    VOLUME_COMMANDED = 'volume_commanded'
    FLOW_RATE_COMMANDED = 'flow_rate_commanded'
    MIN_FLOW_COMMANDED = 'min_flow_commanded'
    TIME_LIMIT = 'time_limit'
    VOLUME_ACTUAL = 'volume'
    FLOW_RATE_ACTUAL = 'flow_rate'
    MIN_FLOW_ACTUAL = 'min_flow'
    TIMER = 'elapsed_time'
    DATE = 'date'
    TIME = 'time_of_day'
    BATTERY = 'battery_voltage'
    CODE = 'code'


# data particle for forward, reverse, and result commands
#  e.g.:
#                      --- command ---   -------- result -------------
#     Result port  |  vol flow minf tlim  |  vol flow minf secs date-time  |  batt code
#        Status 00 |  75 100  25   4 |   1.5  90.7  90.7*  1 031514 001727 | 29.9 0
class RASFLSampleDataParticle(DataParticle):
    _data_particle_type = DataParticleType.RASFL_PARSED

    @staticmethod
    def regex():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        exp = str(r'(Status|Result)' +  # status is incremental, result is the last return from the command
                  '\s*(\d+)\s*\|' +  # PORT
                  '\s*(\d+)' +  # VOLUME_COMMANDED
                  '\s*(\d+)' +  # FLOW RATE COMMANDED
                  '\s*(\d+)' +  # MIN RATE COMMANDED
                  '\s*(\d+)\s*\|' +  # TLIM - TODO
                  '\s*(\d*\.?\d+)' +  # VOLUME (actual)
                  '\s*(\d*\.?\d+)' +  # FLOW RATE (actual)
                  '\s*(\d*\.?\d+)' +  # MIN RATE (actual)
                  '\*?' +
                  '\s*(\d+)' +  # elapsed time (seconds)
                  '\s*(\d+)' +  # MMDDYY (current date)
                  '\s*(\d+)\s*\|' +  # HHMMSS (current time)
                  '\s*(\d*\.?\d+)' +  # voltage (battery)
                  '\s*(\d+)' +  # code enumeration
                  '\s*' + NEWLINE)
        return exp

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(RASFLSampleDataParticle.regex(), re.DOTALL)

    def _build_parsed_values(self):
        match = RASFLSampleDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("RASFL_SampleDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.PUMP_STATUS,
             DataParticleKey.VALUE: match.group(1)},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.PORT,
             DataParticleKey.VALUE: int(match.group(2))},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.VOLUME_COMMANDED,
             DataParticleKey.VALUE: int(match.group(3))},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.FLOW_RATE_COMMANDED,
             DataParticleKey.VALUE: int(match.group(4))},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.MIN_FLOW_COMMANDED,
             DataParticleKey.VALUE: int(match.group(5))},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.TIME_LIMIT,
             DataParticleKey.VALUE: int(match.group(6))},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.VOLUME_ACTUAL,
             DataParticleKey.VALUE: float(match.group(7))},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.FLOW_RATE_ACTUAL,
             DataParticleKey.VALUE: float(match.group(8))},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.MIN_FLOW_ACTUAL,
             DataParticleKey.VALUE: float(match.group(9))},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.TIMER,
             DataParticleKey.VALUE: int(match.group(10))},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.DATE,
             DataParticleKey.VALUE: str(match.group(11))},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.TIME,
             DataParticleKey.VALUE: str(match.group(12))},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.BATTERY,
             DataParticleKey.VALUE: float(match.group(13))},
            {DataParticleKey.VALUE_ID: RASFLSampleDataParticleKey.CODE,
             DataParticleKey.VALUE: int(match.group(14))}]

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
        # replace the driver's discover handler with one that applies the startup values after discovery
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED,
                                         DriverEvent.DISCOVER,
                                         self._handler_connected_discover)

    def _handler_connected_discover(self, event, *args, **kwargs):
        # Redefine discover handler so that we can apply startup params after we discover. 
        # For this instrument the driver puts the instrument into command mode during discover.
        result = SingleConnectionInstrumentDriver._handler_connected_protocol_event(self, event, *args, **kwargs)
        self.apply_startup_params()
        return result

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################

    @staticmethod
    def get_resource_params():
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
                (ProtocolEvent.ENTER, self._handler_unknown_enter),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
                (ProtocolEvent.CLOCK_SYNC, self._handler_sync_clock),
                (ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire),
                (ProtocolEvent.CLEAR, self._handler_command_clear),
                (ProtocolEvent.GET, self._handler_get),
                (ProtocolEvent.SET, self._handler_command_set),
            ],
            ProtocolState.FLUSH: [
                (ProtocolEvent.ENTER, self._handler_flush_enter),
                (ProtocolEvent.FLUSH, self._handler_flush_flush),
                (ProtocolEvent.PUMP_STATUS, self._handler_flush_pump_status),
                (ProtocolEvent.INSTRUMENT_FAILURE, self._handler_all_failure),
            ],
            ProtocolState.FILL: [
                (ProtocolEvent.ENTER, self._handler_fill_enter),
                (ProtocolEvent.FILL, self._handler_fill_fill),
                (ProtocolEvent.PUMP_STATUS, self._handler_fill_pump_status),
                (ProtocolEvent.INSTRUMENT_FAILURE, self._handler_all_failure),
            ],
            ProtocolState.CLEAR: [
                (ProtocolEvent.ENTER, self._handler_clear_enter),
                (ProtocolEvent.CLEAR, self._handler_clear_clear),
                (ProtocolEvent.PUMP_STATUS, self._handler_clear_pump_status),
                (ProtocolEvent.INSTRUMENT_FAILURE, self._handler_all_failure),
            ],
            ProtocolState.RECOVERY: [
                (ProtocolEvent.ENTER, self._handler_recovery_enter),
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
            ],
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # Add build handlers for device commands - we are only using simple commands
        for cmd in Command.list():
            self._add_build_handler(cmd, self._build_command)

        # Add response handlers for device commands.
        self._add_response_handler(Command.BATTERY, self._parse_battery_response)
        self._add_response_handler(Command.CLOCK, self._parse_clock_response)
        self._add_response_handler(Command.PORT, self._parse_port_response)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        self._chunker = StringChunker(Protocol.sieve_function)

        self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.CLOCK_SYNC)

        # Start state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)
        self._sent_cmds = None

        # TODO - reset next_port on mechanical refresh of the PPS filters - how is the driver notified?
        # TODO - need to persist state for next_port to save driver restart
        self.next_port = 1  # next available port

        # self._clock_set_offset = 0
        self._second_attempt = False

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples and status
        """
        matchers = []
        return_list = []

        matchers.append(RASFLSampleDataParticle.regex_compiled())
        matchers.append(RASFLVersionDataParticle.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        # if not return_list:
        #     log.debug("sieve_function: raw_data=%r, return_list=%r", raw_data, return_list)
        return return_list

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        log.debug("_got_chunk:\n%s", chunk)
        sample_dict = self._extract_sample(RASFLSampleDataParticle,
                                           RASFLSampleDataParticle.regex_compiled(), chunk, timestamp)

        if sample_dict:
            self._linebuf = ''
            self._promptbuf = ''
            self._protocol_fsm.on_event(ProtocolEvent.PUMP_STATUS,
                                        RASFLSampleDataParticle.regex_compiled().search(chunk))

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    ########################################################################
    # implement virtual methods from base class.
    ########################################################################

    def apply_startup_params(self):
        """
        Apply startup parameters
        """

        fn = "apply_startup_params"
        config = self.get_startup_config()
        log.debug("%s: startup config = %s", fn, config)

        for param in Parameter.list():
            if param in config:
                self._param_dict.set_value(param, config[param])

        log.debug("%s: new parameters", fn)
        for x in config:
            log.debug("  parameter %s: %s", x, config[x])

    ########################################################################
    # Instrument commands.
    ########################################################################

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        Perform a command-response on the device. Overrides the base class so it will
        return the regular expression groups without concatenating them into a string.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param write_delay kwarg for the amount of delay in seconds to pause
        between each character. If none supplied, the DEFAULT_WRITE_DELAY
        value will be used.
        @param timeout optional wakeup and command timeout via kwargs.
        @param response_regex kwarg with a compiled regex for the response to
        match. Groups that match will be returned as a tuple.
        @retval response The parsed response result.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """

        # Get timeout and initialize response.
        timeout = kwargs.get('timeout', DEFAULT_CMD_TIMEOUT)
        response_regex = kwargs.get('response_regex', None)  # required argument
        write_delay = INTER_CHARACTER_DELAY
        retval = None

        if not response_regex:
            raise InstrumentProtocolException('missing required keyword argument "response_regex"')

        if response_regex and not isinstance(response_regex, RE_PATTERN):
            raise InstrumentProtocolException('Response regex is not a compiled pattern!')

        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            raise InstrumentProtocolException('Cannot build command: %s' % cmd)

        cmd_line = build_handler(cmd, *args)
        # Wakeup the device, pass up exception if timeout

        prompt = self._wakeup(timeout)

        # Clear line and prompt buffers for result.
        self._linebuf = ''
        self._promptbuf = ''

        # Send command.
        log.debug('_do_cmd_resp: %s, timeout=%s, write_delay=%s, response_regex=%s',
                  repr(cmd_line), timeout, write_delay, response_regex)

        for char in cmd_line:
            self._connection.send(char)
            time.sleep(write_delay)

        # Wait for the prompt, prepare result and return, timeout exception
        return self._get_response(timeout, response_regex=response_regex)

    def _do_cmd_home(self):
        """
        Move valve to the home port
        @retval True if successful, False if unable to return home
        """
        func = '_do_cmd_home'
        log.debug('--- djm --- command home')
        port = int(self._do_cmd_resp(Command.PORT, response_regex=Response.PORT)[0])
        log.debug('--- djm --- at port: %d', port)
        if port != 0:
            log.debug('--- djm --- going home')
            self._do_cmd_resp(Command.HOME, response_regex=Response.HOME, timeout=Timeout.HOME)
            port = int(self._do_cmd_resp(Command.PORT, response_regex=Response.PORT)[0])
            if port != 0:
                log.error('Unable to return to home port')
                return False
        return True

    def _do_cmd_flush(self, *args, **kwargs):
        """
        Flush the home port in preparation for collecting a sample. This clears the intake port so that
        the sample taken will be new.
        This only starts the flush. The remainder of the flush is monitored by got_chunk.
        """
        flush_volume = self._param_dict.get_config_value(Parameter.FLUSH_VOLUME)
        flush_flowrate = self._param_dict.get_config_value(Parameter.FLUSH_FLOWRATE)
        flush_minflow = self._param_dict.get_config_value(Parameter.FLUSH_MINFLOW)

        if not self._do_cmd_home():
            self._async_raise_fsm_event(ProtocolEvent.INSTRUMENT_FAILURE)
            return TerminationCodeEnum.STOPPED_BY_USER  # TODO - is the is best error handling method?
        log.debug('--- djm --- flushing home port, %d %d %d',
                  flush_volume, flush_flowrate, flush_flowrate)
        self._do_cmd_no_resp(Command.FORWARD, flush_volume, flush_flowrate, flush_minflow) \
 \
    def _do_cmd_fill(self, *args, **kwargs):
        """
        Fill the sample at the next available port
        """
        log.debug('--- djm --- collecting sample in port %d', self.next_port)
        fill_volume = self._param_dict.get_config_value(Parameter.FILL_VOLUME)
        fill_flowrate = self._param_dict.get_config_value(Parameter.FILL_FLOWRATE)
        fill_minflow = self._param_dict.get_config_value(Parameter.FILL_MINFLOW)

        log.debug('--- djm --- collecting sample in port %d', self.next_port)
        reply = self._do_cmd_resp(Command.PORT, self.next_port, response_regex=Response.PORT)
        log.debug('--- djm --- port returned:\n%r', reply)

        self.next_port += 1  # succeed or fail, we can't use this port again
        # TODO - commit next_port to the agent for persistent data store
        self._do_cmd_no_resp(Command.FORWARD, fill_volume, fill_flowrate, fill_minflow)

    def _do_cmd_clear(self, *args, **kwargs):
        """
        Clear the home port
        """
        self._do_cmd_home()

        clear_volume = self._param_dict.get_config_value(Parameter.REVERSE_VOLUME)
        clear_flowrate = self._param_dict.get_config_value(Parameter.REVERSE_FLOWRATE)
        clear_minflow = self._param_dict.get_config_value(Parameter.REVERSE_MINFLOW)

        log.debug('--- djm --- clearing home port, %d %d %d',
                  clear_volume, clear_flowrate, clear_minflow)
        self._do_cmd_no_resp(Command.REVERSE, clear_volume, clear_flowrate, clear_minflow)

    ########################################################################
    # Generic handlers.
    ########################################################################
    def _handler_pass(self):
        pass

    def _handler_all_failure(self):
        log.error('Instrument failure detected. Entering recovery mode.')
        return ProtocolState.RECOVERY, ResourceAgentState.BUSY

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        # TODO - read persistent data (next port)

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can only be COMMAND (instrument has no actual AUTOSAMPLE mode).
        @retval (next_state, result), (ProtocolState.COMMAND, None) if successful.
        """

        # force to command mode, this instrument has no autosample mode
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        log.debug("_handler_unknown_discover: state = %s", next_state)
        return next_state, next_agent_state

    ########################################################################
    # Flush
    ########################################################################
    def _handler_flush_enter(self):
        """
        Enter the flush state. Trigger FLUSH event.
        """
        log.debug('--- djm --- entering FLUSH state')
        self._second_attempt = False
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._async_raise_fsm_event(ProtocolEvent.FLUSH)

    def _handler_flush_flush(self):
        """
        Begin flushing the home port. Subsequent flushing will be monitored and sent to the flush_pump_status
        handler.
        """
        log.debug('--- djm --- in FLUSH state')
        next_state = ProtocolState.FILL
        next_agent_state = ResourceAgentState.BUSY
        # 2. Set to home port
        # 3. flush intake (home port)
        # 4. wait 30 seconds
        # 1. Get next available port (if no available port, bail)
        log.debug('--- djm --- Flushing home port')
        self._do_cmd_flush()

        return None, (ResourceAgentState.BUSY, None)

    def _handler_flush_pump_status(self, *args):
        """
        Manage pump status update during flush. Status updates indicate continued pumping, Result updates
        indicate completion of command. Check the termination code for success.
        @args match object containing the regular expression match of the status line.
        """
        match = args[0]
        pump_status = match.group(1)
        code = int(match.group(14))

        next_state = None
        next_agent_state = None

        log.debug('--- djm --- received pump status: pump status: %s, code: %d', pump_status, code)
        if pump_status == 'Result':
            log.debug('--- djm --- flush completed - %s', TerminationCodes[code])
            if code == TerminationCodeEnum.SUDDEN_FLOW_OBSTRUCTION:
                log.info('Encountered obstruction during flush, attempting to clear')
                self._async_raise_fsm_event(ProtocolEvent.CLEAR)
            else:
                next_state = ProtocolState.FILL
                next_agent_state = ResourceAgentState.BUSY
        # elif pump_status == 'Status':

        return next_state, next_agent_state

    def _handler_flush_clear(self):
        """
        Attempt to clear home port after stoppage has occurred during flush.
        This is only performed once. On the second stoppage, the driver will enter recovery mode.
        """
        log.debug('--- djm --- handling clear request during flush')
        if self._second_attempt:
            return ProtocolState.RECOVERY, ResourceAgentState.BUSY

        self._second_attempt = True
        self._do_cmd_clear()

        return None, None

    ########################################################################
    # Fill
    ########################################################################
    def _handler_fill_enter(self, *args):
        """
        Enter the fill state. Trigger FILL event.
        """
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._async_raise_fsm_event(ProtocolEvent.FILL)

    def _handler_fill_fill(self, *args):
        """
        Send the fill command and process the first response
        """
        next_state = None
        next_agent_state = None
        result = None

        log.debug('Entering PHIL PHIL')
        # 5. switch to collection port (next available)
        # 6. collect sample (4000 ml)
        # 7. wait 2 minutes
        if self.next_port > NUM_PORTS:
            log.error('Unable to collect RAS sample - %d containers full', NUM_PORTS)
            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.COMMAND
        else:
            self._do_cmd_fill()

        return next_state, (next_agent_state, result)

    def _handler_fill_pump_status(self, *args):
        """
        Process pump status updates during filter collection.
        """
        next_state = None
        next_agent_state = None

        match = args[0]
        pump_status = match.group(1)
        code = int(match.group(14))

        if pump_status == 'Result':
            if code != TerminationCodeEnum.VOLUME_REACHED:
                next_state = ProtocolState.RECOVERY
            next_state = ProtocolState.CLEAR  # all done
            # if pump_status == 'Status':
            # TODO - check for bag rupture (> 93% flow rate near end of sample collect- RAS only)

        return next_state, next_agent_state

    ########################################################################
    # Clear
    ########################################################################
    def _handler_clear_enter(self, args):
        """
        Enter the clear state. Trigger the CLEAR event.
        """
        self._second_attempt = False
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._async_raise_fsm_event(ProtocolEvent.CLEAR)

    def _handler_clear_clear(self, *args):
        """
        Send the clear command. If there is an obstruction trigger a FLUSH, otherwise place driver in RECOVERY mode.
        """
        log.debug('--- djm --- clearing home port')

        # 8. return to home port
        # 9. reverse flush 75 ml to pump water from exhaust line through intake line
        self._do_cmd_clear()
        return None, None

    def _handler_clear_pump_status(self, *args):
        """
        Parse pump status during clear action.
        """
        next_state = None
        next_agent_state = None

        match = args[0]
        pump_status = match.group(1)
        code = int(match.group(14))

        if pump_status == 'Result':
            if code != TerminationCodeEnum.VOLUME_REACHED:
                log.error('Encountered obstruction during clear. Attempting flush...')
                self._async_raise_fsm_event(ProtocolEvent.FLUSH)
            else:
                log.debug('--- djm --- clear complete')
                next_state = ProtocolState.COMMAND
                next_agent_state = ResourceAgentState.COMMAND
        # if Status, nothing to do
        return next_state, next_agent_state

    def _handler_clear_flush(self, *args):
        """
        Attempt to recover from failed attempt to clear by flushing home port. Only try once.
        """
        log.info('Attempting to flush main port during clear')
        if self._second_attempt:
            return ProtocolState.RECOVERY, ResourceAgentState.BUSY

        self._second_attempt = True
        self._do_cmd_flush()
        return None, None

    ########################################################################
    # Command handlers.
    # just implemented to make DA possible, instrument has no actual command mode
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        """
        # Command device to update parameters and send a config change event if needed.
        self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_set(self, *args, **kwargs):
        """
        Process command  # TODO - what commands get sent?
        """
        log.debug('--- djm --- entered _handler_command_set with args: %s', args)
        next_state = None
        result = None
        return next_state, result

    def _handler_command_start_direct(self, *args, **kwargs):
        """
        Start direct access.
        """
        log.debug('--- djm --- entered _handler_command_start_direct with args: %s', args)
        result = None
        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS

        return next_state, (next_agent_state, result)

    ########################################################################
    # Recovery handlers.
    ########################################################################

    # TODO - not sure how to determine how to exit from this state. Probably requires a driver reset.
    def _handler_recovery_enter(self):
        """
        Error recovery mode. The instrument failed to respond to a command and now requires the user to perform
        diagnostics and correct before proceeding.
        """
        log.debug('--- djm --- entered recovery mode')
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

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
        next_state = None
        result = None

        self._do_cmd_direct(data)

        return next_state, result

    def _handler_direct_access_stop_direct(self, *args, **kwargs):
        result = None
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return next_state, (next_agent_state, result)

    ########################################################################
    # general handlers.
    ########################################################################

    def get_timestamp_delayed(self, fmt, delay=0):
        """
        Return a formatted date string of the current utc time,
        but the string return is delayed until the next second
        transition.

        Formatting:
        http://docs.python.org/library/time.html#time.strftime

        @param fmt: strftime() format string
        @return: formatted date string
        @raise ValueError if format is None
        """
        if not fmt:
            raise ValueError

        now = datetime.datetime.utcnow() + datetime.timedelta(seconds=delay)
        time.sleep((1e6 - now.microsecond) / 1e6)
        now = datetime.datetime.utcnow() + datetime.timedelta(seconds=delay)
        return now.strftime(fmt)

    def _handler_sync_clock(self, *args, **kwargs):
        """
        sync clock close to a second edge 
        @retval (next_state, (next_agent_state, result)) tuple, (None, (None, None)).
        @throws InstrumentTimeoutException if device respond correctly.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        cmd_len = len('clock 03/20/2014 17:14:55' + NEWLINE)
        delay = cmd_len * INTER_CHARACTER_DELAY

        time_format = "%m/%d/%Y %H:%M:%S"
        str_val = self.get_timestamp_delayed(time_format, delay)
        # str_val = time.strftime(time_format, time.gmtime(time.time() + self._clock_set_offset))
        log.debug("Setting instrument clock to '%s'", str_val)

        try:
            ras_time = self._do_cmd_resp(Command.CLOCK, str_val, response_regex=Response.READY)[0]
            log.debug('--- djm --- ras_time: %r', ras_time)
            ras_time = time.strptime(ras_time + 'UTC', '%m/%d/%y %H:%M:%S %Z')
            log.debug('--- djm --- ras_time: %r', ras_time)
            current_time = time.gmtime()
            log.debug('--- djm --- current_time: %s', current_time)
            diff = time.mktime(current_time) - time.mktime(ras_time)
            log.info('clock synched within %d seconds', diff)
            #latency = diff / 2
        finally:
            pass

        return None, (None, ras_time)

    def _handler_command_acquire(self, *args, **kwargs):
        return ProtocolState.FLUSH, ResourceAgentState.BUSY

    def _handler_command_clear(self, *args, **kwargs):
        reply = None
        # TODO - reply = do_cmd_clear(self)
        return None, (None, reply)

    ########################################################################
    # Private helpers.
    ########################################################################

    def _wakeup(self, wakeup_timeout=10, response_timeout=3):
        """
        Over-written because waking this instrument up is a multi-step process with
        two different requests required
        @param wakeup_timeout The timeout to wake the device.
        @param response_timeout The time to look for response to a wakeup attempt.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        sleep_time = .1
        command = Command.GO

        # Grab start time for overall wakeup timeout.
        starttime = time.time()

        while True:
            # Clear the prompt buffer.
            log.debug("_wakeup: clearing promptbuf: %s", self._promptbuf)
            self._promptbuf = ''

            # Send a command and wait delay amount for response.
            log.debug('_wakeup: Sending command %s, delay=%s', command.encode("hex"), response_timeout)
            for char in command:
                self._connection.send(char)
                time.sleep(INTER_CHARACTER_DELAY)
            sleep_amount = 0
            while True:
                time.sleep(sleep_time)
                if self._promptbuf.find(Prompt.COMMAND_INPUT) != -1:
                    # instrument is awake
                    log.debug('_wakeup: got command input prompt %s', Prompt.COMMAND_INPUT)
                    # add inter-character delay which _do_cmd_resp() incorrectly doesn't add to
                    # the start of a transmission
                    time.sleep(INTER_CHARACTER_DELAY)
                    return Prompt.COMMAND_INPUT
                if self._promptbuf.find(Prompt.ENTER_CTRL_C) != -1:
                    command = Command.CONTROL_C
                    break
                if self._promptbuf.find(Prompt.PERIOD) == 0:
                    command = Command.CONTROL_C
                    break
                sleep_amount += sleep_time
                if sleep_amount >= response_timeout:
                    log.debug("_wakeup: expected response not received, buffer=%s", self._promptbuf)
                    break

            if time.time() > starttime + wakeup_timeout:
                raise InstrumentTimeoutException(
                    "_wakeup(): instrument failed to wakeup in %d seconds time" % wakeup_timeout)

    def _build_command(self, cmd, *args):
        return cmd + ' ' + ' '.join([str(x) for x in args]) + NEWLINE

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, False)

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.CLOCK_SYNC, display_name="synchronize clock")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with XR-420 parameters.
        For each parameter key add value formatting function for set commands.
        """
        # The parameter dictionary.
        self._param_dict = ProtocolParameterDict()

        # Add parameter handlers to parameter dictionary for instrument configuration parameters.
        self._param_dict.add(Parameter.FLUSH_VOLUME,
                             r'Flush Volume: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             # default_value=150,
                             default_value=10,  # djm - fast test value
                             units='mL',
                             startup_param=True,
                             display_name="flush_volume",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FLUSH_FLOWRATE,
                             r'Flush Flow Rate: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=100,
                             units='mL/sec',
                             startup_param=True,
                             display_name="flush_flow_rate",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FLUSH_MINFLOW,
                             r'Flush Min Flow: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=75,
                             units='mL/sec',
                             startup_param=True,
                             display_name="flush_min_flow",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FILL_VOLUME,
                             r'Fill Volume: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             # default_value=4000,
                             default_value=10,  # djm - fast test value
                             units='mL',
                             startup_param=True,
                             display_name="fill_volume",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FILL_FLOWRATE,
                             r'Fill Flow Rate: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=100,
                             units='mL/sec',
                             startup_param=True,
                             display_name="fill_flow_rate",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FILL_MINFLOW,
                             r'Fill Min Flow: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=75,
                             units='mL/sec',
                             startup_param=True,
                             display_name="fill_min_flow",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.REVERSE_VOLUME,
                             r'Reverse Volume: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             # default_value=100,
                             default_value=10,  # djm - fast test value
                             units='mL',
                             startup_param=True,
                             display_name="reverse_volume",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.REVERSE_FLOWRATE,
                             r'Reverse Flow Rate: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=100,
                             units='mL/sec',
                             startup_param=True,
                             display_name="reverse_flow_rate",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.REVERSE_MINFLOW,
                             r'Reverse Min Flow: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=75,
                             units='mL/sec',
                             startup_param=True,
                             display_name="reverse_min_flow",
                             visibility=ParameterDictVisibility.IMMUTABLE)

    def _update_params(self):
        """
        Update the parameter dictionary. 
        """

        log.debug("_update_params:")

    def _parse_battery_response(self, response, prompt):
        """
        Parse handler for battery command.
        @param response command response string.
        @param prompt prompt following command response.        
        @throws InstrumentProtocolException if battery command misunderstood.
        """
        log.debug("_parse_battery_response: response=%s, prompt=%s", response, prompt)
        if prompt == Prompt.UNRECOGNIZED_COMMAND:
            raise InstrumentProtocolException('battery command not recognized: %s.' % response)

        if not self._param_dict.update(response):
            raise InstrumentProtocolException('battery command not parsed: %s.' % response)

        return

    def _parse_clock_response(self, response, prompt):
        """
        Parse handler for clock command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if clock command misunderstood.
        @retval the joined string from the regular expression match
        """
        # extract current time from response
        log.debug('--- djm --- parse_clock_response: response: %r', response)
        ras_time_string = ' '.join(response.split()[:2])
        time_format = "%m/%d/%y %H:%M:%S"
        ras_time = time.strptime(ras_time_string, time_format)
        ras_time = list(ras_time)
        ras_time[-1] = 0  # tm_isdst field set to 0 - using GMT, no DST

        return tuple(ras_time)

    def _parse_port_response(self, response, prompt):
        """
        Parse handler for port command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if port command misunderstood.
        @retval the joined string from the regular expression match
        """
        # extract current port from response
        log.debug('--- djm --- parse_port_response: response: %r', response)
        port = int(response)

        return port
