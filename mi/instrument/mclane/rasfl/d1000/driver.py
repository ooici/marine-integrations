"""
@package mi.instrument.mclane.ras.ooicore.driver
@file marine-integrations/mi/instrument/mclane/ras/ooicore/driver.py
@author Dan Mergens
@brief Driver for the D1000 (D1421)
Release notes:

initial version
"""
import functools

from mi.core.driver_scheduler import \
    DriverSchedulerConfigKey, \
    TriggerType
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict
from mi.core.util import dict_equal


__author__ = 'Dan Mergens'
__license__ = 'Apache 2.0'

import re

from mi.core.log import get_logger

log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, \
    InstrumentParameterException

from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.chunker import StringChunker

from mi.core.instrument.instrument_driver import \
    SingleConnectionInstrumentDriver, \
    DriverEvent, \
    DriverAsyncEvent, \
    DriverConfigKey, \
    DriverProtocolState, \
    DriverParameter, \
    ResourceAgentState

from mi.core.instrument.data_particle import \
    DataParticle, \
    DataParticleKey, \
    CommonDataParticleType

from mi.core.instrument.driver_dict import DriverDictKey

from mi.core.instrument.protocol_param_dict import ProtocolParameterDict, \
    ParameterDictType, \
    ParameterDictVisibility


NEWLINE = '\r\n'
# NEWLINE = '\r'

# default timeout.
INTER_CHARACTER_DELAY = .2

####
#    Driver Constant Definitions
####

DEFAULT_SAMPLE_RATE = 15  # once every 6 seconds
MIN_SAMPLE_RATE = 1  # 1 second
MAX_SAMPLE_RATE = 3600  # 1 hour


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
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    # rate at which to stream temperature reports
    SAMPLE_INTERVAL = 'output_period'

    # # Factory default: 0x31070182
    # # Lab default:     0x310214C2
    # # Byte 1 - identifies the module channel address
    # # default: 0x31 ('1')
    # CHANNEL_ADDRESS = 'channel_address'
    #
    # # Byte 2
    # # Bit 7 - when true, the D1000 will generate line feeds, should be false for driver
    # # default: 0
    # LINEFEED = 'linefeed'
    # # Bit 6 - parity type (0 - even, 1 - odd)
    # # default: 0
    # PARITY_TYPE = 'parity_type'
    # # Bit 5 - parity enabled flag
    # # default: 0
    # PARITY_ENABLE = 'parity_enable'
    # # Bit 4 - addressing mode (0- normal, 1- extended)
    # # default: 0
    # EXTENDED_ADDRESSING = 'addressing_mode'
    # # Bits 3-0 - baud rate (9- 57600, 8- 115200, 7- 300, 6- 600, 5- 1200, 4- 2400, 3- 4800, 2-9600, 1- 19200, 0-38400)
    # # default: 2 (9600)
    # BAUD_RATE = 'baud_rate'
    #
    # # Byte 3
    # # Bit 7 - enable alarm
    # # default: 0
    # ALARM_ENABLE = 'alarm_enable'
    # # Bit 6 - low alarm latch (0- momentary, 1- latching) see also $LO
    # # default: 0
    # LOW_ALARM_LATCH = 'low_alarm_latching'
    # # Bit 5 - high alarm latch (0- momentary, 1- latching) see also $HI
    # # default: 0
    # HIGH_ALARM_LATCH = 'high_alarm_latching'
    # # Bit 4 - 3/4 wire select - must match RTD configuration (0- 3 wire, 1- 4 wire)
    # # default: 1
    # RTD_4_WIRE = 'rtd_34_wire'
    # # Bit 3 - temperature output scaling (0- celsius, 1- fahrenheit) - must change HI/LO to match after
    # # default: 0
    # TEMP_UNITS = 'fahrenheit_select'
    # # Bit 2 - echo for daisy-chained configuration
    # # default: 1
    # ECHO = 'echo_commands'
    # # Bits 1-0 - units of delay in the response (based on baud rate)
    # # default: 0
    # COMMUNICATION_DELAY = 'delay'
    #
    # # Byte 4
    # # Bits 7-6 - data output precision (0- 4 digits, 1- 5, 2- 6, 3- 7)
    # # default: 3 (7)
    # PRECISION = 'output_precision'
    # # Bits 5-3 - (0- no filter, 1- .25, 2- .5, 3- 1, 4- 2, 5- 4, 6- 8, 7- 16)
    # # default: 0 (no filter)
    # LARGE_SIGNAL_FILTER_C = 'large_filter_signal_constant'
    # # Bits 2-0 - (0- no filter, 1- .25, 2- .5, 3- 1, 4- 2, 5- 4, 6- 8, 7- 16)
    # # Should be larger than the large signal filter constant value
    # # default: 2 (0.5)
    # SMALL_SIGNAL_FILTER_C = 'small_filter_signal_constant'
    # # HI_ALARM_1 = "hi_alarm_1"
    # # HI_ALARM_2 = "hi_alarm_2"
    # # HI_ALARM_3 = "hi_alarm_3"
    # # LO_ALARM_1 = "lo_alarm_1"
    # # LO_ALARM_2 = "lo_alarm_2"
    # # LO_ALARM_3 = "lo_alarm_3"


class Command(BaseEnum):
    """
    Instrument command strings - case sensitive
    """
    READ_1 = '#1RD'  # temperature probe 1
    READ_2 = '#2RD'  # temperature probe 2
    READ_3 = '#3RD'  # temperature probe 3
    ENABLE_WRITE_1 = '#1WE'
    ENABLE_WRITE_2 = '#2WE'
    ENABLE_WRITE_3 = '#3WE'
    DEFAULT_SETUP_1 = '#1SU310214C2'
    DEFAULT_SETUP_2 = '#2SU320214C2'
    DEFAULT_SETUP_3 = '#3SU330214C2'


class Prompt(BaseEnum):
    """
    Device i/o prompts.
    """
    CR_NL = '\r\n'


class ScheduledJob(BaseEnum):
    SAMPLE = 'scheduled_sample'


class Response(BaseEnum):
    """
    Expected device response strings
    """
    # *1RD+00019.16AB
    TEMP = re.compile(r'\*[123]RD')
    ENABLE_WRITE_1 = re.compile(r'\*1WEF7')
    ENABLE_WRITE_2 = re.compile(r'\*2WEF8')
    ENABLE_WRITE_3 = re.compile(r'\*3WEF9')
    DEFAULT_SETUP_1 = re.compile(r'\*1SU310214C2A3')
    DEFAULT_SETUP_2 = re.compile(r'\*2SU320214C2A5')
    DEFAULT_SETUP_3 = re.compile(r'\*3SU330214C2A7')


class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW
    D1000_PARSED = 'D1000_parsed'


###############################################################################
# Data Particles
###############################################################################

class D1000TemperatureDataParticleKey(BaseEnum):
    TEMP1 = 'temperature1'
    TEMP2 = 'temperature2'
    TEMP3 = 'temperature3'


class D1000TemperatureDataParticle(DataParticle):
    _data_particle_type = DataParticleType.D1000_PARSED

    @staticmethod
    def regex():
        # exp = r'\*([123])RD([+-]\d*\.?\d+)(\w{2})' + NEWLINE
        exp = \
            r'\*1RD([+-]\d*\.?\d+)(\w{2})' + NEWLINE + r'.*?' + \
            r'\*2RD([+-]\d*\.?\d+)(\w{2})' + NEWLINE + r'.*?' + \
            r'\*3RD([+-]\d*\.?\d+)(\w{2})' + NEWLINE
        return exp

    @staticmethod
    def regex_compiled():
        return re.compile(D1000TemperatureDataParticle.regex(), re.DOTALL)

    def _checksum(self):
        for line in self.raw_data.split(NEWLINE):
            if line.startswith('*'):
                cksum = int(line[-2:], 16)  # checksum is last two characters in ASCII hex
                data = line[:-2]  # remove checksum from data

                total = sum([ord(x) for x in data])
                calc_cksum = total & 0xff
                log.debug('checksum (%r): %d (calculated: %d)', line, cksum, calc_cksum)
                if cksum != calc_cksum:
                    raise SampleException('Checksum failed - temperature sample is corrupt: %s', self.raw_data)

    def _build_parsed_values(self):
        match = self.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("D1000TemperatureDataParticle: No regex match of parsed sample data: [%s]",
                                  self.raw_data)

        self._checksum()

        result = [
            {DataParticleKey.VALUE_ID: D1000TemperatureDataParticleKey.TEMP1,
             DataParticleKey.VALUE: float(match.group(1))},
            {DataParticleKey.VALUE_ID: D1000TemperatureDataParticleKey.TEMP2,
             DataParticleKey.VALUE: float(match.group(3))},
            {DataParticleKey.VALUE_ID: D1000TemperatureDataParticleKey.TEMP3,
             DataParticleKey.VALUE: float(match.group(5))},
        ]

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
                (ProtocolEvent.EXIT, self._handler_unknown_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_command_exit),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
                (ProtocolEvent.ACQUIRE_SAMPLE, self._handler_sample),
                (ProtocolEvent.START_AUTOSAMPLE, self._handler_command_autosample),
                # (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.GET, self._handler_get),
                (ProtocolEvent.SET, self._handler_command_set),
            ],
            ProtocolState.AUTOSAMPLE: [
                (ProtocolEvent.ENTER, self._handler_autosample_enter),
                (ProtocolEvent.ACQUIRE_SAMPLE, self._handler_sample),
                (ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop),
                (ProtocolEvent.EXIT, self._handler_autosample_exit),
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_direct_access_exit),
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
        # self._add_response_handler(Command.xyz, self._parse_xyz_response)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        self._chunker = StringChunker(Protocol.sieve_function)

        # Start state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)
        self._sent_cmds = None

        self._do_cmd_resp = functools.partial(CommandResponseInstrumentProtocol._do_cmd_resp, self,
                                              write_delay=INTER_CHARACTER_DELAY)
        self.initialize_scheduler()

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples and status
        """
        matchers = []
        return_list = []

        matchers.append(D1000TemperatureDataParticle.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        if not return_list:
            log.debug("sieve_function: raw_data=%s, return_list=%s", raw_data, return_list)
        return return_list

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        log.debug("_got_chunk: chunk=%s", chunk)
        self._extract_sample(D1000TemperatureDataParticle, D1000TemperatureDataParticle.regex_compiled(), chunk,
                             timestamp)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    ########################################################################
    # implement virtual methods from base class.
    ########################################################################

    def _set_params(self, *args, **kwargs):
        """
        Issue commands to the instrument to set various parameters.  If
        startup is set to true that means we are setting startup values
        and immutable parameters can be set.  Otherwise only READ_WRITE
        parameters can be set.

        must be overloaded in derived classes

        @param params dictionary containing parameter name and value pairs
        @param startup flag - true indicates initializing, false otherwise
        """

        log.debug('_set_params - called with args: %r', args[0])
        params = args[0]

        # check for attempt to set readonly parameters (read-only or immutable set outside startup)
        self._verify_not_readonly(*args, **kwargs)
        log.debug('_set_params - verified parameter is not read only')
        old_config = self._param_dict.get_config()

        for (key, val) in params.iteritems():
            log.debug("KEY = " + str(key) + " VALUE = " + str(val))
            self._param_dict.set_value(key, val)

        new_config = self._param_dict.get_config()
        log.debug('new config: %s\nold config: %s', new_config, old_config)
        # check for parameter change
        if not dict_equal(old_config, new_config):
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

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
        pass

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
        self._cmd_dict = ProtocolCommandDict()

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with XR-420 parameters.
        For each parameter key add value formatting function for set commands.
        """
        # The parameter dictionary.
        self._param_dict = ProtocolParameterDict()

        # Add parameter handlers to parameter dictionary for instrument configuration parameters.
        self._param_dict.add(Parameter.SAMPLE_INTERVAL,
                             r'Output Periodicity: (.*) sec',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=DEFAULT_SAMPLE_RATE,
                             startup_param=True,
                             display_name='D1000 sample periodicity (sec)',
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.set_value(Parameter.SAMPLE_INTERVAL, DEFAULT_SAMPLE_RATE)

    def _update_params(self):
        """
        Update the parameter dictionary. 
        """

        log.debug("_update_params:")

    ########################################################################
    # Event handlers for UNKNOWN state.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        log.debug('entering driver state: %s from %s', ProtocolState.UNKNOWN, self.get_current_state())
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, current state), (ProtocolState.COMMAND, None) if successful.
        """

        # force to command mode, this instrument has no autosample mode
        next_state = ProtocolState.COMMAND
        result = ResourceAgentState.COMMAND

        log.debug("_handler_unknown_discover: state = %s", next_state)
        return ProtocolState.COMMAND, ResourceAgentState.IDLE

    ########################################################################
    # Event handlers for COMMAND state.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        """
        log.debug('entering driver state: %s from %s', ProtocolState.COMMAND, self.get_current_state())

        # Command device to update parameters and send a config change event if needed.
        self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_command_set(self, *args, **kwargs):
        """
        no writable parameters so does nothing, just implemented to make framework happy
        """
        log.debug('_handler_command_set - called with args %r', args[0])

        input_params = args[0]

        for key, value in input_params.items():
            log.debug('_handler_command_set - key (%r) value (%r)', key, value)
            if not Parameter.has(key):
                raise InstrumentParameterException('Invalid parameter supplied to set: %s' % key)

            try:
                value = int(value)
            except TypeError:
                raise InstrumentParameterException('Invalid value [%s] for parameter %s' % (value, key))

            if key == Parameter.SAMPLE_INTERVAL:
                if value < MIN_SAMPLE_RATE or value > MAX_SAMPLE_RATE:
                    raise InstrumentParameterException('Parameter %s value [%d] is out of range [%d %d]' %
                                                       (key, value, MIN_SAMPLE_RATE, MAX_SAMPLE_RATE))
        startup = False
        try:
            startup = args[1]
        except IndexError:
            pass

        self._set_params(input_params, startup)

        return None, None
        # return None, (None, None)

    def _handler_command_autosample(self, *args, **kwargs):
        """
        Begin autosample.
        """
        return ProtocolState.AUTOSAMPLE, (ResourceAgentState.STREAMING, None)

    def _handler_command_start_direct(self, *args, **kwargs):
        """
        """
        return ProtocolState.DIRECT_ACCESS, (ResourceAgentState.DIRECT_ACCESS, None)

    ########################################################################
    # Event handlers for AUTOSAMPLE state.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Start auto polling the temperature sensors.
        """
        log.debug('entering driver state: %s from %s', ProtocolState.AUTOSAMPLE, self.get_current_state())

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._protocol_fsm.on_event(ProtocolEvent.ACQUIRE_SAMPLE)

        job_name = ScheduledJob.SAMPLE
        config = {
            DriverConfigKey.SCHEDULER: {
                job_name: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.SECONDS: self._param_dict.get(Parameter.SAMPLE_INTERVAL)
                    }
                }
            }
        }
        self.set_init_params(config)
        if self._scheduler is not None:
            log.debug('--- djm --- there you are')
        log.debug('--- djm --- adding sample job')
        self._add_scheduler_event(ScheduledJob.SAMPLE, ProtocolEvent.ACQUIRE_SAMPLE)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Stop autosampling - remove the scheduled autosample
        """
        log.debug('--- djm --- _handler_autosample_exit')

        if self._scheduler is not None:
            try:
                log.debug('--- djm --- tearing down sample job')
                self._remove_scheduler(ScheduledJob.SAMPLE)
            except KeyError:
                log.debug('_remove_scheduler count not find: %s', ScheduledJob.SAMPLE)
        else:
            log.error('--- djm --- where for art thou missing scheduler?')

    def _handler_sample(self, *args, **kwargs):
        """
        Poll the three temperature probes for current temperature readings.
        """
        log.debug('--- djm --- _handler_autosample_sample')
        self._do_cmd_resp(Command.READ_1, response_regex=Response.TEMP)
        self._do_cmd_resp(Command.READ_2, response_regex=Response.TEMP)
        self._do_cmd_resp(Command.READ_3, response_regex=Response.TEMP)

        return None, (None, None)

    def _handler_autosample_stop(self, *args, **kwargs):
        """
        Terminate autosampling
        """
        log.debug('--- djm --- _handler_autosample_stop')
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """
        log.debug('entering driver state: %s from %s', ProtocolState.DIRECT_ACCESS, self.get_current_state())
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        # restore D1000 to default state
        self._do_cmd_resp(Command.ENABLE_WRITE_1, response_regex=Response.ENABLE_WRITE_1)
        self._do_cmd_resp(Command.DEFAULT_SETUP_1, response_regex=Response.DEFAULT_SETUP_1)
        self._do_cmd_resp(Command.ENABLE_WRITE_2, response_regex=Response.ENABLE_WRITE_2)
        self._do_cmd_resp(Command.DEFAULT_SETUP_2, response_regex=Response.DEFAULT_SETUP_2)
        self._do_cmd_resp(Command.ENABLE_WRITE_3, response_regex=Response.ENABLE_WRITE_3)
        self._do_cmd_resp(Command.DEFAULT_SETUP_3, response_regex=Response.DEFAULT_SETUP_3)

    def _handler_direct_access_execute_direct(self, data):
        self._do_cmd_direct(data)

        return None, (None, None)

    def _handler_direct_access_stop_direct(self, *args, **kwargs):
        result = None
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        # return next_state, (next_agent_state, result)
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)
