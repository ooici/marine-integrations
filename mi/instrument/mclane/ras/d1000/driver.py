"""
@package mi.instrument.mclane.ras.ooicore.driver
@file marine-integrations/mi/instrument/mclane/ras/ooicore/driver.py
@author Dan Mergens
@brief Driver for the D1000 (D1421)
Release notes:

initial version
"""
import functools
import math
from types import FunctionType

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
    InstrumentParameterException, InstrumentProtocolException, InstrumentTimeoutException

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
    CommonDataParticleType

from mi.core.instrument.driver_dict import DriverDictKey

from mi.core.instrument.protocol_param_dict import ProtocolParameterDict, \
    ParameterDictType, \
    ParameterDictVisibility


NEWLINE = '\r'

# default timeout.
INTER_CHARACTER_DELAY = .2

####
#    Driver Constant Definitions
####

DEFAULT_SAMPLE_RATE = 15  # sample periodicity in seconds
MIN_SAMPLE_RATE = 1  # in seconds
MAX_SAMPLE_RATE = 3600  # in seconds (1 hour)


class LoggingMetaClass(type):
    def __new__(mcs, class_name, bases, class_dict):
        new_class_dict = {}
        for attributeName, attribute in class_dict.items():
            if type(attribute) == FunctionType:
                attribute = log_method(attribute)  # replace with a wrapped version of method
            new_class_dict[attributeName] = attribute
        return type.__new__(mcs, class_name, bases, new_class_dict)


def log_method(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        log.debug('entered %s | args: %r | kwargs: %r', func.__name__, args, kwargs)
        r = func(*args, **kwargs)
        log.debug('exiting %s | returning %r', func.__name__, r)
        return r

    return inner


def checksum(data):
    """
    Calculate checksum on value string.
    @retval checksum - base 10 integer representing last two hexadecimal digits of the checksum
    """
    total = sum([ord(x) for x in data])
    return total & 0xff


def valid_response(line):
    """
    Perform a checksum calculation on provided data. The checksum used for comparison is the last two characters of
    the line.
    @param line - response line from the instrument, must start with '*'
    @retval checksum validity - whether or not the checksum provided in the line matches calculated checksum
    """
    cksum = int(line[-2:], 16)  # checksum is last two characters in ASCII hex
    data = line[:-2]  # remove checksum from data

    calc_cksum = checksum(data)
    if cksum != calc_cksum:
        log.debug('checksum failed (%r): should be %s', line, hex(calc_cksum))
        return False
    return True


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


    # baud rate (9- 57600, 8- 115200, 7- 300, 6- 600, 5- 1200, 4- 2400, 3- 4800, 2-9600, 1- 19200, 0-38400)


class BaudRate(BaseEnum):
    BAUD_38400 = 0
    BAUD_19200 = 1
    BAUD_9600 = 2
    BAUD_4800 = 3
    BAUD_2400 = 4
    BAUD_1200 = 5
    BAUD_600 = 6
    BAUD_300 = 7
    BAUD_115200 = 8
    BAUD_57600 = 9


class AlarmType(BaseEnum):
    MOMENTARY = 0
    LATCHING = 1


class RTDSelect(BaseEnum):
    RTD_3_WIRE = 0
    RTD_4_WIRE = 1


class UnitPrecision(BaseEnum):
    """
    Data output precision (0- 4 digits, 1- 5, 2- 6, 3- 7)
    """
    DIGITS_4 = 0
    DIGITS_5 = 1
    DIGITS_6 = 2
    DIGITS_7 = 3


    # (0- no filter, 1- .25, 2- .5, 3- 1, 4- 2, 5- 4, 6- 8, 7- 16)


def filter_enum(value):
    if value == 0:
        return 0
    return math.log(value) / math.log(2) + 3


def filter_value(enum_value):
    if enum_value == 0:
        return 0
    return 2 ** (enum_value - 3)


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    # rate at which to stream temperature reports
    SAMPLE_INTERVAL = 'output_period'

    # Factory default: 0x31070182
    # Lab default:     0x310214C2
    # Byte 1 - identifies the module channel address
    # default: 0x31 ('1')
    CHANNEL_ADDRESS = 'channel_address'

    # Byte 2
    # Bit 7 - when true, the D1000 will generate line feeds, should be false for driver
    # default: 0
    LINEFEED = 'linefeed'
    # Bit 6 - parity type (0 - even, 1 - odd)
    # default: 0
    PARITY_TYPE = 'parity_type'
    # Bit 5 - parity enabled flag
    # default: 0
    PARITY_ENABLE = 'parity_enable'
    # Bit 4 - addressing mode (0- normal, 1- extended)
    # default: 0
    EXTENDED_ADDRESSING = 'addressing_mode'
    # Bits 3-0 - baud rate (9- 57600, 8- 115200, 7- 300, 6- 600, 5- 1200, 4- 2400, 3- 4800, 2-9600, 1- 19200, 0-38400)
    # default: 2 (9600)
    BAUD_RATE = 'baud_rate'

    # Byte 3
    # Bit 7 - enable alarm
    # default: 0
    ALARM_ENABLE = 'alarm_enable'
    # Bit 6 - low alarm latch (0- momentary, 1- latching) see also $LO
    # default: 0
    LOW_ALARM_LATCH = 'low_alarm_latching'
    # Bit 5 - high alarm latch (0- momentary, 1- latching) see also $HI
    # default: 0
    HIGH_ALARM_LATCH = 'high_alarm_latching'
    # Bit 4 - 3/4 wire select - must match RTD configuration (0- 3 wire, 1- 4 wire)
    # default: 1
    RTD_4_WIRE = 'rtd_34_wire'
    # Bit 3 - temperature output scaling (0- celsius, 1- fahrenheit) - must change HI/LO to match after
    # default: 0
    TEMP_UNITS = 'fahrenheit_select'
    # Bit 2 - echo for daisy-chained configuration
    # default: 1
    ECHO = 'echo_commands'
    # Bits 1-0 - units of delay in the response (based on baud rate)
    # default: 0
    COMMUNICATION_DELAY = 'delay'

    # Byte 4
    # Bits 7-6 - data output precision (0- 4 digits, 1- 5, 2- 6, 3- 7)
    # default: 3 (7)
    PRECISION = 'output_precision'
    # Bits 5-3 - (0- no filter, 1- .25, 2- .5, 3- 1, 4- 2, 5- 4, 6- 8, 7- 16)
    # default: 0 (no filter)
    LARGE_SIGNAL_FILTER_C = 'large_filter_signal_constant'
    # Bits 2-0 - (0- no filter, 1- .25, 2- .5, 3- 1, 4- 2, 5- 4, 6- 8, 7- 16)
    # Should be larger than the large signal filter constant value
    # default: 2 (0.5)
    SMALL_SIGNAL_FILTER_C = 'small_filter_signal_constant'


class Command(BaseEnum):
    """
    Instrument command strings - case sensitive
    """
    READ = 'RD'
    ENABLE_WRITE = 'WE'
    SETUP = 'SU'
    READ_SETUP = 'RS'
    CLEAR_ZERO = 'CZ'


class Prompt(BaseEnum):
    """
    Device i/o prompts.
    """
    CR_NL = '\r\n'
    CR = '\r'


class ScheduledJob(BaseEnum):
    SAMPLE = 'scheduled_sample'


class Response(BaseEnum):
    """
    Expected device response strings
    """
    # *1RD+00019.16AB
    READ = re.compile(r'\*[123]RD')
    ENABLE_WRITE = re.compile(r'\*[123]WE')
    SETUP = re.compile(r'\*[123]SU')
    READ_SETUP = re.compile(r'\*[123]RS')
    CLEAR_ZERO = re.compile(r'\*[123]CZ')


class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW
    D1000_PARSED = 'D1000_sample'


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

    def _build_parsed_values(self):
        match = self.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("D1000TemperatureDataParticle: No regex match of parsed sample data: [%s]",
                                  self.raw_data)

        for line in self.raw_data.split(NEWLINE):
            if line.startswith('*'):
                if not valid_response(line):
                    raise SampleException('Checksum failed - temperature sample is corrupt: %s', self.raw_data)

        result = [
            self._encode_value(D1000TemperatureDataParticleKey.TEMP1, match.group(1), float),
            self._encode_value(D1000TemperatureDataParticleKey.TEMP2, match.group(3), float),
            self._encode_value(D1000TemperatureDataParticleKey.TEMP3, match.group(5), float),
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
    __metaclass__ = LoggingMetaClass

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
            self._add_response_handler(cmd, self._check_command)
        self._add_build_handler(Command.SETUP, self._build_setup_command)
        self._add_response_handler(Command.READ_SETUP, self._read_setup_response_handler)

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

        self.initialize_scheduler()

        # unit identifiers - must match the setup command (SU31 - '1')
        self._units = ['1', '2', '3']

        self._setup = None  # set by the read setup command handler for comparison to see if the config needs reset

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
        @param startup - a flag, true indicates initializing, false otherwise
        """

        params = args[0]

        # check for attempt to set readonly parameters (read-only or immutable set outside startup)
        self._verify_not_readonly(*args, **kwargs)
        old_config = self._param_dict.get_config()

        for (key, val) in params.iteritems():
            log.debug("KEY = " + str(key) + " VALUE = " + str(val))
            self._param_dict.set_value(key, val)

        new_config = self._param_dict.get_config()
        # check for parameter change
        if not dict_equal(old_config, new_config):
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def apply_startup_params(self):
        """
        Apply startup parameters
        """

        config = self.get_startup_config()

        for param in Parameter.list():
            if param in config:
                self._param_dict.set_value(param, config[param])

    ########################################################################
    # Private helpers.
    ########################################################################

    def _wakeup(self, wakeup_timeout=10, response_timeout=3):
        """
        Over-ridden because the D1000 does not go to sleep and requires no special wake-up commands.
        @param wakeup_timeout The timeout to wake the device.
        @param response_timeout The time to look for response to a wakeup attempt.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        pass

    def _do_command(self, cmd, unit, **kwargs):
        """
        Send command and ensure it matches appropriate response. Simply enforces sending the unit identifier as a
        required argument.
        @param cmd - Command to send to instrument
        @param unit - unit identifier
        @retval - response from instrument
        """
        self._do_cmd_resp(cmd, unit, write_delay=INTER_CHARACTER_DELAY, **kwargs)

    def _build_command(self, cmd, unit):
        """
        @param cmd - Command to process
        @param unit - unit identifier
        """
        return '#' + unit + cmd + NEWLINE

    def _build_setup_command(self, cmd, unit):
        """
        @param cmd - command to send - should be 'SU'
        @param unit - unit identifier - should be '1', '2', or '3', must be a single character
        """
        # use defaults - in the future, may consider making some of these parameters
        # byte 0
        channel_address = unit
        # byte 1
        line_feed = self._param_dict.format(Parameter.LINEFEED)
        parity_type = self._param_dict.format(Parameter.PARITY_TYPE)
        parity_enable = self._param_dict.format(Parameter.PARITY_ENABLE)
        extended_addressing = self._param_dict.format(Parameter.EXTENDED_ADDRESSING)
        baud_rate = self._param_dict.format(Parameter.BAUD_RATE)
        baud_rate = getattr(BaudRate, 'BAUD_%d' % baud_rate, BaudRate.BAUD_9600)
        # byte 2
        alarm_enable = self._param_dict.format(Parameter.ALARM_ENABLE)
        low_alarm_latch = self._param_dict.format(Parameter.LOW_ALARM_LATCH)
        high_alarm_latch = self._param_dict.format(Parameter.HIGH_ALARM_LATCH)
        rtd_wire = self._param_dict.format(Parameter.RTD_4_WIRE)
        temp_units = self._param_dict.format(Parameter.TEMP_UNITS)
        echo = self._param_dict.format(Parameter.ECHO)
        delay_units = self._param_dict.format(Parameter.COMMUNICATION_DELAY)
        #byte 3
        precision = self._param_dict.format(Parameter.PRECISION)
        precision = getattr(UnitPrecision, 'DIGITS_%d' % precision, UnitPrecision.DIGITS_6)
        large_signal_filter_constant = self._param_dict.format(Parameter.LARGE_SIGNAL_FILTER_C)
        large_signal_filter_constant = filter_enum(large_signal_filter_constant)
        small_signal_filter_constant = self._param_dict.format(Parameter.SMALL_SIGNAL_FILTER_C)
        small_signal_filter_constant = filter_enum(small_signal_filter_constant)

        # # Factory default: 0x31070182
        # # Lab default:     0x310214C2

        byte_0 = int(channel_address.encode("hex"), 16)
        log.debug('byte 0: %s', byte_0)
        byte_1 = \
            (line_feed << 7) + \
            (parity_type << 6) + \
            (parity_enable << 5) + \
            (extended_addressing << 4) + \
            baud_rate
        log.debug('byte 1: %s', byte_1)
        byte_2 = \
            (alarm_enable << 7) + \
            (low_alarm_latch << 6) + \
            (high_alarm_latch << 5) + \
            (rtd_wire << 4) + \
            (temp_units << 3) + \
            (echo << 2) + \
            delay_units
        log.debug('byte 2: %s', byte_2)
        byte_3 = \
            (precision << 6) + \
            (large_signal_filter_constant << 3) + \
            small_signal_filter_constant
        log.debug('byte 3: %s', byte_3)

        setup_command = '#%sSU%02x%02x%02x%02x' % (unit[0], byte_0, byte_1, byte_2, byte_3) + NEWLINE
        log.debug('default setup command (%r) for unit %02x (%s)' % (setup_command, byte_0, unit[0]))
        return setup_command

    def _check_command(self, resp, prompt):
        """
        Perform a checksum calculation on provided data. The checksum used for comparison is the last two characters of
        the line.
        @param resp - response from the instrument to the command
        @param prompt - expected prompt (or the joined groups from a regex match)
        @retval
        """
        for line in resp.split(NEWLINE):
            if line.startswith('?'):
                raise InstrumentProtocolException('error processing command (%r)', resp[1:])
            if line.startswith('*'):  # response
                if not valid_response(line):
                    raise InstrumentProtocolException('checksum failed (%r)', line)

    def _read_setup_response_handler(self, resp, prompt):
        """
        Save the setup.
        @param resp - response from the instrument to the command
        @param prompt - expected prompt (or the joined groups from a regex match)
        """
        self._check_command(resp, prompt)
        self._setup = resp

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

    def _add_setup_param(self, name, fmt, **kwargs):
        """
        Add setup command to the parameter dictionary. All 'SU' parameters are not startup parameter, but should be
        restored upon return from direct access. These parameters are all part of the instrument command 'SU'.
        """
        self._param_dict.add(name, '', None, fmt,
                             startup_param=False,
                             direct_access=True,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             **kwargs)

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with XR-420 parameters.
        For each parameter key add value formatting function for set commands.
        """
        # The parameter dictionary.
        self._param_dict = ProtocolParameterDict()

        # Add parameter handlers to parameter dictionary for instrument configuration parameters.
        self._param_dict.add(Parameter.SAMPLE_INTERVAL,
                             '',  # this is a driver only parameter
                             None,
                             int,
                             type=ParameterDictType.INT,
                             default_value=DEFAULT_SAMPLE_RATE,
                             startup_param=True,
                             display_name='D1000 sample periodicity (sec)',
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._add_setup_param(Parameter.CHANNEL_ADDRESS,
                              int,
                              display_name='base channel address',
                              type=ParameterDictType.INT,
                              default_value=0x31)
        self._add_setup_param(Parameter.LINEFEED,
                              bool,
                              display_name='line feed flag',
                              type=ParameterDictType.BOOL,
                              default_value=False)
        self._add_setup_param(Parameter.PARITY_TYPE,
                              bool,
                              display_name='parity type',
                              type=ParameterDictType.BOOL,
                              default_value=False)
        self._add_setup_param(Parameter.PARITY_ENABLE,
                              bool,
                              display_name='parity flag',
                              type=ParameterDictType.BOOL,
                              default_value=False)
        self._add_setup_param(Parameter.EXTENDED_ADDRESSING,
                              bool,
                              display_name='extended addressing',
                              type=ParameterDictType.BOOL,
                              default_value=False)
        self._add_setup_param(Parameter.BAUD_RATE,
                              int,
                              display_name='baud rate',
                              type=ParameterDictType.INT,
                              default_value=9600)
        self._add_setup_param(Parameter.ALARM_ENABLE,
                              bool,
                              display_name='enable alarms',
                              type=ParameterDictType.BOOL,
                              default_value=False)
        self._add_setup_param(Parameter.LOW_ALARM_LATCH,
                              bool,
                              display_name='low alarm latching',
                              type=ParameterDictType.BOOL,
                              default_value=False)
        self._add_setup_param(Parameter.HIGH_ALARM_LATCH,
                              bool,
                              display_name='high alarm latching',
                              type=ParameterDictType.BOOL,
                              default_value=False)
        self._add_setup_param(Parameter.RTD_4_WIRE,
                              bool,
                              display_name='4 wire RTD flag',
                              type=ParameterDictType.BOOL,
                              default_value=True)
        self._add_setup_param(Parameter.TEMP_UNITS,
                              bool,
                              display_name='Fahrenheit flag',
                              type=ParameterDictType.BOOL,
                              default_value=False)
        self._add_setup_param(Parameter.ECHO,
                              bool,
                              display_name='daisy chain',
                              type=ParameterDictType.BOOL,
                              default_value=True)
        self._add_setup_param(Parameter.COMMUNICATION_DELAY,
                              int,
                              display_name='communication delay',
                              type=ParameterDictType.INT,
                              default_value=0)
        self._add_setup_param(Parameter.PRECISION,
                              int,
                              display_name='precision',
                              type=ParameterDictType.INT,
                              default_value=6)
        self._add_setup_param(Parameter.LARGE_SIGNAL_FILTER_C,
                              float,
                              display_name='large signal filter constant',
                              type=ParameterDictType.FLOAT,
                              default_value=0.0)
        self._add_setup_param(Parameter.SMALL_SIGNAL_FILTER_C,
                              float,
                              display_name='small signal filter constant',
                              type=ParameterDictType.FLOAT,
                              default_value=0.50)

        for key in self._param_dict.get_keys():
            self._param_dict.set_default(key)

    def _update_params(self):
        """
        Update the parameter dictionary. 
        """
        pass

    def _restore_params(self):
        """
        Restore D1000, clearing any alarms and set-point.
        """
        # make sure the alarms are disabled - preferred over doing setup, then clear alarms commands
        self._param_dict.set_value(Parameter.ALARM_ENABLE, False)
        for i in self._units:
            current_setup = None  # set in READ_SETUP response handler
            try:
                self._do_command(Command.READ_SETUP, i, response_regex=Response.READ_SETUP)
                current_setup = self._setup[4:][:-2]  # strip off the leader and checksum
            except InstrumentTimeoutException:
                log.error('D1000 unit %s has been readdressed, unable to restore settings' % i[0])
            new_setup = self._build_setup_command(Command.SETUP, i)[4:]  # strip leader (no checksum)
            if not current_setup == new_setup:
                log.debug('restoring setup to default state (%s) from current state (%s)', new_setup, current_setup)
                self._do_command(Command.ENABLE_WRITE, i)
                self._do_command(Command.SETUP, i)
            self._do_command(Command.ENABLE_WRITE, i)
            self._do_command(Command.CLEAR_ZERO, i)

    ########################################################################
    # Event handlers for UNKNOWN state.
    ########################################################################

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

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, current state), (ProtocolState.COMMAND, None) if successful.
        """

        # force to command mode, this instrument has no autosample mode
        next_state = ProtocolState.COMMAND
        result = ResourceAgentState.COMMAND

        return ProtocolState.COMMAND, ResourceAgentState.IDLE

    ########################################################################
    # Event handlers for COMMAND state.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        """
        # Command device to update parameters and send a config change event if needed.
        self._restore_params()

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
        input_params = args[0]

        for key, value in input_params.items():
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
        self._add_scheduler_event(ScheduledJob.SAMPLE, ProtocolEvent.ACQUIRE_SAMPLE)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Stop autosampling - remove the scheduled autosample
        """
        if self._scheduler is not None:
            try:
                self._remove_scheduler(ScheduledJob.SAMPLE)
            except KeyError:
                log.debug('_remove_scheduler count not find: %s', ScheduledJob.SAMPLE)

    def _handler_sample(self, *args, **kwargs):
        """
        Poll the three temperature probes for current temperature readings.
        """
        for i in self._units:
            self._do_command(Command.READ, i)

        return None, (None, None)

    def _handler_autosample_stop(self, *args, **kwargs):
        """
        Terminate autosampling
        """
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)

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
        self._do_cmd_direct(data)

        return None, (None, None)

    def _handler_direct_access_stop_direct(self, *args, **kwargs):
        result = None
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        # return next_state, (next_agent_state, result)
        return ProtocolState.COMMAND, (ResourceAgentState.COMMAND, None)
