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


import re
import string

from mi.core.driver_scheduler import DriverSchedulerConfigKey, TriggerType
from mi.core.exceptions import SampleException, InstrumentProtocolException, InstrumentParameterException
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.instrument.protocol_param_dict import ParameterDictType

from mi.core.log import get_logger;

log = get_logger()

from mi.core.common import BaseEnum
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


# newline.
NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 10

###
#    Driver Constant Definitions
###

class ScheduledJob(BaseEnum):
    ACQUIRE_SAMPLE = 'acquire_sample'
    CONFIGURATION_DATA = "configuration_data"


class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW
    THSPH_PARSED = 'thsph_sample'


class Command(BaseEnum):
    AH = 'aH*'  # Gets data sample from ADC
    AP = 'aP*'  # Communication test, returns aP#


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE


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
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
    SET = ProtocolEvent.SET


class Parameter(DriverParameter):
    """
    Device specific parameters for THSPH.
    """
    INTERVAL = 'SampleInterval'
    OUTPUT_FORMAT = "OutputFormat"


class Prompt(BaseEnum):
    """
    Device i/o prompts for THSPH
    """
    COMMAND = 'S>'


class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """


###############################################################################
# Data Particles
###############################################################################
class THSPHDataParticleKey(BaseEnum):
    IMPEDANCE_ELECTRODE_1 = "hiie1"  # High input impedance electrode
    IMPEDANCE_ELECTRODE_2 = "hiie2"  # High input impedance electrode
    H2_ELECTRODE = "h2electrode"  # H2 electrode
    S2_ELECTRODE = "s2electrode"  # S2- electrode
    THERMO1 = "thermocouple1"  # Type E thermocouple 1-high
    THERMO2 = "thermocouple2"  # Type E thermocouple 2-low
    THERMISTOR = "thermistor"  # Thermistor
    BOARD_THERMISTOR = "bthermistor"  # Board Thermistor


class DataParticle(object):
    pass


class THSPHParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    The data signal is a concatenation of 8 channels of 14-bit resolution data.
    Each channel is output as a four ASCII character hexadecimal number (0000 to 3FFF).
    Each channel, 1-8, should be parsed as a 4 character hexadecimal number and converted to a raw decimal number.

    Sample:
       aH12341234123412341234123412341234#

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

        pattern = r'aH'  # pattern starts with 'aH'
        pattern += r'([0-9A-F]{4})'  # Chanel 1 High Input Impedance Electrode
        pattern += r'([0-9A-F]{4})'  # Chanel 2 High Input Impedance Electrode
        pattern += r'([0-9A-F]{4})'  # H2 Electrode
        pattern += r'([0-9A-F]{4})'  # S2 Electrode
        pattern += r'[0-9A-F]{4}'  # Type E Thermocouple 1
        pattern += r'([0-9A-F]{4})'  # Type E Thermocouple 2
        pattern += r'([0-9A-F]{4})'  # Thermistor
        pattern += r'([0-9A-F]{4})'  # Board Thermocouple
        pattern = r'#'  # pattern ends with '#'
        pattern += NEWLINE
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
        Type E Thermocouple 2, Thermistor, Board Thermistor
        
        @throws SampleException If there is a problem with sample creation
        """
        match = THSPHParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            electrode1 = self.hex2value(match.group(1))
            electrode2 = self.hex2value(match.group(2))
            h2electrode = self.hex2value(match.group(3))
            s2electrode = self.hex2value(match.group(4))
            thermocouple1 = self.hex2value(match.group(5))
            thermocouple2 = self.hex2value(match.group(6))
            thermistor = self.hex2value(match.group(7))
            board_thermistor = self.hex2value(match.group(8))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

        result = [{DataParticleKey.VALUE_ID: THSPHDataParticleKey.IMPEDANCE_ELECTRODE_1,
                   DataParticleKey.VALUE: electrode1},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.IMPEDANCE_ELECTRODE_2,
                   DataParticleKey.VALUE: electrode2},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.H2_ELECTRODE,
                   DataParticleKey.VALUE: h2electrode},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.S2_ELECTRODE,
                   DataParticleKey.VALUE: s2electrode},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.THERMO1,
                   DataParticleKey.VALUE: thermocouple1},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.THERMO2,
                   DataParticleKey.VALUE: thermocouple2},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.THERMISTOR,
                   DataParticleKey.VALUE: thermistor},
                  {DataParticleKey.VALUE_ID: THSPHDataParticleKey.BOARD_THERMISTOR,
                   DataParticleKey.VALUE: board_thermistor}]

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
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE,
                                       self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE,
                                       self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.START_AUTOSAMPLE,
                                       self._handler_autosample_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE,
                                       self._handler_autosample_stop_autosample)


        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_driver_dict()
        self._build_command_dict()
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(Command.AH, self._build_simple_command)
        self._add_build_handler(Command.AP, self._build_simple_command)


        # Add response handlers for device commands.

        # Add sample handlers.

        # State state machine in COMMAND state.
        self._protocol_fsm.start(ProtocolState.COMMAND)

        # commands sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        #
        self._chunker = StringChunker(THSPHProtocol.sieve_function)

        # Schedule autosample task
        self._add_scheduler_event(ScheduledJob.ACQUIRE_SAMPLE, ProtocolEvent.ACQUIRE_SAMPLE)


    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        matchers = []
        return_list = []

        matchers.append(THSPHParticle.regex_compiled())

        for matcher in matchers:
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
        self._cmd_dict.add(Capability.TEST, display_name="test")
        self._cmd_dict.add(Capability.SET, display_name="set")

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
                             default_value=5)


    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]


    ########################################################################
    # Command handlers.
    ########################################################################
    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Get device status
        """
        next_state = None
        next_agent_state = None
        result = None
        log.debug("_handler_command_acquire_sample")

        self._do_cmd_no_resp(Command.AH, timeout=TIMEOUT)

        log.debug("Sending AH Cmd")

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

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """
        next_state = None
        result = None

        return (next_state, result)

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """
        next_state = None
        result = None

        return (next_state, result)

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
        next_state = None
        next_agent_state = None
        result = None

        self._start_logging(*args, **kwargs)

        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return (next_state, (next_agent_state, result))

    #######################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state. Start the scheduled task using the
        sample interval parameter
        """
        next_state = None
        next_agent_state = None
        result = None

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        # Start the scheduler to poll the instrument for
        # data every sample interval seconds
        job_name = ScheduledJob.ACQUIRE_STATUS
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
        #self.set_init_params(config)
        self._scheduler.add_config(config)

        # Start the scheduled task using the sample interval parameter ?????
        self.initialize_scheduler()

        return (next_state, (next_agent_state, result))


    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state. Remove the autosample task
        """
        next_state = None
        next_agent_state = None
        result = None

        # Stop the Auto Poll scheduling
        self._remove_scheduler(ScheduledJob.ACQUIRE_SAMPLE)

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        return (next_state, (next_agent_state, result))

    def _handler_autosample_start_autosample(self, *args, **kwargs):
        pass

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Remove the autosample task. Exit Autosample state
        """
        next_state = None
        next_agent_state = None
        result = None

        # Stop the Auto Poll scheduling
        self._remove_scheduler(ScheduledJob.ACQUIRE_SAMPLE)

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        return (next_state, (next_agent_state, result))

    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        result = None
        log.debug("_handler_command_start_direct: entering DA mode")
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
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        pass

    def _handler_direct_access_execute_direct(self, data):
        """
        """
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


    def _setup_interval_config(self):
        """
        Set up an interval configuration and add it to the scheduler.
        """
        job_name = ScheduledJob.ACQUIRE_STATUS
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
        #self.set_init_params(config)
        self._scheduler.add_config(config)
