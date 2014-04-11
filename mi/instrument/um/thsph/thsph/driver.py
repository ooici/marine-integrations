"""
@package mi.instrument.um.thsph.thsph.driver
@file marine-integrations/mi/instrument/um/thsph/thsph/driver.py
@author Richard Han
@brief Driver for the thsph
Release notes:

Vent Chemistry Instrument  Driver


"""
__author__ = 'Richard Han'
__license__ = 'Apache 2.0'

import time
import re
import string

from mi.core.driver_scheduler import DriverSchedulerConfigKey, TriggerType
from mi.core.exceptions import SampleException, InstrumentProtocolException, InstrumentParameterException, \
    InstrumentTimeoutException
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.instrument.protocol_param_dict import ParameterDictType

from mi.core.log import get_logger;

log = get_logger()

from mi.core.common import BaseEnum, InstErrorCode
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver, DriverConfigKey
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker

###
#    Driver Constant Definitions
###

# newline.
NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 10

# Maximum number of communication test to wake up the instrument
MAX_COMM_TEST = 2

# Time wait for the instrument response
CMD_RESP_TIME = .1

#The timeout to wake the device
WAKEUP_TIMEOUT = 3

# The time to look for response to a wake up attempt
RESPONSE_TIMEOUT = 1

class ScheduledJob(BaseEnum):
    AUTO_SAMPLE = 'auto_sample'


class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW
    THSPH_PARSED = 'thsph_sample'


class Command(BaseEnum):
    """
    Instrument command strings
    """
    GET_SAMPLE = 'aH*'  # Gets data sample from ADC
    COMM_TEST = 'aP*'   # Communication test, returns aP#


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
    DISCOVER = DriverEvent.DISCOVER
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    GET = DriverEvent.GET
    SET = DriverEvent.SET


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET


class Parameter(DriverParameter):
    """
    Device specific parameters for THSPH.
    """
    INTERVAL = 'SampleInterval'


class Prompt(BaseEnum):
    """
    Device i/o prompts for THSPH
    """
    COMM_RESPONSE = 'aP#'


###############################################################################
# Data Particles
###############################################################################
class THSPHDataParticleKey(BaseEnum):
    HIGH_IMPEDANCE_ELECTRODE_1 = "hie1"   # High Impedance Electrode 1 for pH
    HIGH_IMPEDANCE_ELECTRODE_2 = "hie2"   # High Impedance Electrode 2 for pH
    H2_ELECTRODE = "h2electrode"          # H2 electrode
    S2_ELECTRODE = "s2electrode"          # Sulfide Electrode
    THERMOCOUPLE1 = "thermocouple1"       # Type E thermocouple 1-high
    THERMOCOUPLE2 = "thermocouple2"       # Type E thermocouple 2-low
    REFERENCE_THERMISTOR = "rthermistor"  # Reference Thermistor
    BOARD_THERMISTOR = "bthermistor"      # Board Thermistor


class THSPHParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    The data signal is a concatenation of 8 channels of 14-bit resolution data.
    Each channel is output as a four ASCII character hexadecimal number (0000 to 3FFF).
    Each channel, 1-8, should be parsed as a 4 character hexadecimal number and converted
    to a raw decimal number.

    Sample:
       aH200A200720DE20AA10883FFF2211225E#

    Format:
       aHaaaabbbbccccddddeeeeffffgggghhhh#

       aaaa = Chanel 1 High Input Impedance Electrode;
       bbbb = Chanel 2 High Input Impedance Electrode;
       cccc = H2 Electrode;
       dddd = S2 Electrode;
       eeee = TYPE E Thermocouple 1;
       ffff = TYPE E Thermocouple 2;
       gggg = Thermistor;
       hhhh Board 2 Thermistor;

    """
    _data_particle_type = DataParticleType.THSPH_PARSED

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'aH'              # pattern starts with 'aH'
        pattern += r'([0-9A-F]{4})'  # Chanel 1 High Input Impedance Electrode
        pattern += r'([0-9A-F]{4})'  # Chanel 2 High Input Impedance Electrode
        pattern += r'([0-9A-F]{4})'  # H2 Electrode
        pattern += r'([0-9A-F]{4})'  # S2 Electrode
        pattern += r'([0-9A-F]{4})'  # Type E Thermocouple 1
        pattern += r'([0-9A-F]{4})'  # Type E Thermocouple 2
        pattern += r'([0-9A-F]{4})'  # Reference Thermistor
        pattern += r'([0-9A-F]{4})'  # Board Thermocouple
        pattern += r'#'              # pattern ends with '#'
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(THSPHParticle.regex())

    def _build_parsed_values(self):
        """
        Take something in the ADC data format and split it into
        Chanel 1 High Input Impedance Electrode, Chanel 2 High Input
        Impedance Electrode, H2 Electrode, S2 Electrode, Type E Thermocouple 1,
        Type E Thermocouple 2, Reference Thermistor, Board Thermistor
        
        @throws SampleException If there is a problem with sample creation
        """
        match = THSPHParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of THSPH parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            electrode1 = self.hex2value(match.group(1))
            electrode2 = self.hex2value(match.group(2))
            h2electrode = self.hex2value(match.group(3))
            s2electrode = self.hex2value(match.group(4))
            thermocouple1 = self.hex2value(match.group(5))
            thermocouple2 = self.hex2value(match.group(6))
            ref_thermistor = self.hex2value(match.group(7))
            board_thermistor = self.hex2value(match.group(8))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

        result = [{DataParticleKey.VALUE_ID: THSPHDataParticleKey.HIGH_IMPEDANCE_ELECTRODE_1,
                   DataParticleKey.VALUE: electrode1},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.HIGH_IMPEDANCE_ELECTRODE_2,
                   DataParticleKey.VALUE: electrode2},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.H2_ELECTRODE,
                   DataParticleKey.VALUE: h2electrode},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.S2_ELECTRODE,
                   DataParticleKey.VALUE: s2electrode},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.THERMOCOUPLE1,
                   DataParticleKey.VALUE: thermocouple1},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.THERMOCOUPLE2,
                   DataParticleKey.VALUE: thermocouple2},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.REFERENCE_THERMISTOR,
                   DataParticleKey.VALUE: ref_thermistor},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.BOARD_THERMISTOR,
                   DataParticleKey.VALUE: board_thermistor}]

        return result


    def hex2value(self, hex_value, divisor=None):
        """
        Convert a ADC hex value to an int value.  If a divisor is passed in as
        a parameter, the int value will be divided by the divisor.
        @param hex_value: string to convert
        @param divisor: conversion value
        @return: int or float of the converted value
        """

        if not isinstance(hex_value, str):
            raise InstrumentParameterException("hex value not a string")

        if divisor != None and divisor == 0:
            raise InstrumentParameterException("divisor can not be 0")

        value = int(hex_value, 16)
        if(divisor != None):
            return float(value) / divisor
        else:
            return value


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
        self._protocol = THSPHProtocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

class THSPHProtocol(CommandResponseInstrumentProtocol):
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
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE,
                                       self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE,
                                       self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT,
                                       self._handler_command_start_direct)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_SAMPLE,
                                       self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.START_AUTOSAMPLE,
                                       self._handler_autosample_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE,
                                       self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_driver_dict()
        self._build_command_dict()
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(Command.GET_SAMPLE, self._build_simple_command)
        self._add_build_handler(Command.COMM_TEST, self._build_simple_command)

        # Add response handlers for device commands.

        # State state machine in COMMAND state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(THSPHProtocol.sieve_function)


    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        matchers = []
        return_list = []

        matchers.append(THSPHParticle.regex_compiled())

        for matcher in matchers:
            log.debug('matcher: %r raw_data: %r', matcher.pattern, raw_data)
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list


    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        if not (self._extract_sample(THSPHParticle, THSPHParticle.regex_compiled(), chunk, timestamp)):
            raise InstrumentProtocolException("Unhandled chunk")

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="start autosample")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="stop autosample")
        self._cmd_dict.add(Capability.ACQUIRE_SAMPLE, display_name="acquire sample")
        self._cmd_dict.add(Capability.SET, display_name="set")
        self._cmd_dict.add(Capability.GET, display_name="get")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with THSPH parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """

        # Add parameter handlers to parameter dict.
        self._param_dict.add(Parameter.INTERVAL,
                             r'Auto Polled Interval = (\d+)',
                             lambda match: int(match.group(1)),
                             str,
                             type=ParameterDictType.INT,
                             display_name="Polled Interval",
                             startup_param=True,
                             direct_access=False,
                             default_value=1)


    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]


    ########################################################################
    # Unknown State handlers.
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
        Discover current state; Change next state to be COMMAND state.
        @retval (next_state, result).
        """
        log.debug('_handler_unknown_discover ')

        next_state = ProtocolState.COMMAND
        result = ResourceAgentState.IDLE

        return next_state, result

    ########################################################################
    # Command State handlers.
    ########################################################################
    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Get device status
        """
        log.debug("_handler_command_acquire_sample")

        next_state = None
        next_agent_state = None
        result = None

        self._do_cmd_no_resp(Command.GET_SAMPLE, timeout=TIMEOUT)

        return (next_state, (next_agent_state, result))

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass


    def _handler_command_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.  First we set a baseline timestamp
        that all data expirations will be calculated against.  Then we try to get parameter
        value.  If we catch an expired parameter then we will update all parameters and get
        values using the original baseline time that we set at the beginning of this method.
        Assuming our _update_params is updating all parameter values properly then we can
        ensure that all data will be fresh.  Nobody likes stale data!
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @raise InstrumentParameterException if missing or invalid parameter.
        @raise InstrumentParameterExpirationException If we fail to update a parameter
        on the second pass this exception will be raised on expired data
        """
        log.debug("_handler_command_get enter ")
        return self._handler_get(*args, **kwargs)

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

        log.debug("_handler_command_set enter ")
        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
        try:
            params = args[0]

        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')

        try:
            startup = args[1]
        except IndexError:
            pass

        old_config = self._param_dict.get_config()
        self._set_params(params, startup)

        new_config = self._param_dict.get_config()
        if old_config != new_config :
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

        return (next_state, result)


    def _set_params(self, *args, **kwargs):
        """
        Set various parameters internally to the driver. No issuing commands to the
        instrument needed for this driver.
        """
        log.debug("_set_params ")
        try:
            params = args[0]
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        # Sampling interval is the only parameter that is set by the driver.
        # Do a range check before we start all sets
        for (key, val) in params.iteritems():
            if(key == Parameter.INTERVAL and val not in range(1,601)):
                log.debug("Auto Sample Interval not in 1 to 600 range ")
                raise InstrumentParameterException("sample interval out of range")
            log.debug('key = (%s), value = (%s)' % (key, val))

        self._param_dict.set_value(Parameter.INTERVAL, params[Parameter.INTERVAL])


    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass


    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        (next_agent_state, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        log.debug("_handler_command_start_autosample ")

        next_state = None
        next_agent_state = None
        result = None

        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return (next_state, (next_agent_state, result))


    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        log.debug("_handler_command_start_direct ")

        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        result = None

        log.debug("_handler_command_start_direct: entering DA mode")
        return (next_state, (next_agent_state, result))

    #######################################################################
    # Autosample State handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state  Because this is an instrument that must be
        polled we need to ensure the scheduler is added when we are in an
        autosample state.  This scheduler raises events to poll the
        instrument for data.
        """
        log.debug("_handler_autosample_enter ")

        next_state = None
        next_agent_state = None
        result = None

        self._init_params()

        self._setup_autosample_config()

        # Schedule auto sample task
        self._add_scheduler_event(ScheduledJob.AUTO_SAMPLE, ProtocolEvent.ACQUIRE_SAMPLE)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        return (next_state, (next_agent_state, result))


    def _setup_autosample_config(self):
        """
        Set up auto sample configuration and add it to the scheduler.
        """
        # Start the scheduler to poll the instrument for
        # data every sample interval seconds

        log.debug("_setup_autosample_config")
        job_name = ScheduledJob.AUTO_SAMPLE
        polled_interval = self._param_dict.get_config_value(Parameter.INTERVAL)
        config = {
            DriverConfigKey.SCHEDULER: {
                job_name: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.SECONDS: polled_interval
                    }
                }
            }
        }
        self.set_init_params(config)

        #self._scheduler.add_config(config)

        # Start the scheduler if it is not running
        if not self._scheduler:
            self.initialize_scheduler()


    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit auto sample state. Remove the auto sample task
        """
        log.debug("_handler_autosample_exit ")

        next_state = None
        next_agent_state = None
        result = None

        return (next_state, (next_agent_state, result))

    def _handler_autosample_start_autosample(self, *args, **kwargs):
        pass

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Remove the auto sample task. Exit Auto sample state
        """
        log.debug("_handler_autosample_stop_autosample ")

        next_state = None
        next_agent_state = None
        result = None

        # Stop the Auto Poll scheduling
        self._remove_scheduler(ScheduledJob.AUTO_SAMPLE)

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND
        return (next_state, (next_agent_state, result))


    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        log.debug("_handler_direct_access_enter ")

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        pass


    def _handler_direct_access_execute_direct(self, data):
        """
        Execute direct command
        """
        log.debug("_handler_direct_access_execute_direct: data = %s" % data)

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

        log.debug("_handler_direct_access_stop_direct ")

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))


    def _build_simple_command(self, cmd):
        """
        Build handler for basic THSPH commands.
        @param cmd the simple thsph command to format.
        @retval The command to be sent to the device.
        """
        return "%s%s" % (cmd, NEWLINE)

    def _build_set_command(self, cmd, param, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        try:
            str_val = self._param_dict.format(param, val)

            if param == 'INTERVAL':
                param = 'sampleinterval'

            set_cmd = '%s=%s' % (param, str_val)
            set_cmd = set_cmd + NEWLINE

        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return set_cmd


    def _wakeup(self, wakeup_timeout=WAKEUP_TIMEOUT, response_timeout=RESPONSE_TIMEOUT):
        """
        waking this instrument up by sending MAX_COM_TEST communication test commands
        (aP*)
        @param wakeup_timeout The timeout to wake the device.
        @param response_timeout The time to look for response to a wakeup attempt.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        log.debug("_wakeup ")

        sleep_time = CMD_RESP_TIME
        cmd = Command.COMM_TEST
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            log.error('_wakeup: no handler for command: %s' % (cmd))
            raise InstrumentProtocolException(error_code=InstErrorCode.BAD_DRIVER_COMMAND)
        cmd_line = build_handler(cmd)

        # Grab start time for overall wakeup timeout.
        start_time = time.time()
        test_count = 0;
        while test_count < MAX_COMM_TEST:
            # Clear the prompt buffer.
            self._promptbuf = ''

            # Send a communication test command and wait delay amount for response.
            self._connection.send(cmd_line)
            time.sleep(sleep_time)
            if self._promptbuf.find(Prompt.COMM_RESPONSE) != -1:
                # instrument is awake
                log.debug('_wakeup: got communication test response %s', Prompt.COMM_RESPONSE)
                test_count += 1
            else:
                #clear test_count since we want MAX_COMM_TEST consecutive successful communication test
                test_count = 0;
            # Stop wake up the instrument if the wake up time out has elapsed
            if time.time() > start_time + wakeup_timeout:
                break;

        if test_count != MAX_COMM_TEST:
            log.debug('instrument failed to wakeup in %d seconds time' % wakeup_timeout)
            raise InstrumentTimeoutException(
                    "_wakeup(): instrument failed to wakeup in %d seconds time" % wakeup_timeout)

        else:
            return Prompt.COMM_RESPONSE

