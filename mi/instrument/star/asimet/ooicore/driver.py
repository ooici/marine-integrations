"""
@package mi.instrument.star.asimet.ooicore.driver
@file marine-integrations/mi/instrument/star/asimet/ooicore/driver.py
@author Bill Bollenbacher
@brief Driver for the ooicore
Release notes:

initial version
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

import re
import time
import string

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, \
                               InstrumentProtocolException
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict, \
                                                   ParameterDictType, \
                                                   ParameterDictVisibility

# newline.
NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 10
        
####
#    Driver Constant Definitions
####

class ScheduledJob(BaseEnum):
    ACQUIRE_STATUS = 'acquire_status'
    CLOCK_SYNC = 'clock_sync'
    AUTOSAMPLE = 'autosample'

class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN       = DriverProtocolState.UNKNOWN
    COMMAND       = DriverProtocolState.COMMAND
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER            = DriverEvent.ENTER
    EXIT             = DriverEvent.EXIT
    DISCOVER         = DriverEvent.DISCOVER
    EXECUTE_DIRECT   = DriverEvent.EXECUTE_DIRECT
    START_DIRECT     = DriverEvent.START_DIRECT
    STOP_DIRECT      = DriverEvent.STOP_DIRECT
    GET              = DriverEvent.GET
    SET              = DriverEvent.SET
    ACQUIRE_SAMPLE   = DriverEvent.ACQUIRE_SAMPLE
    ACQUIRE_STATUS   = DriverEvent.ACQUIRE_STATUS
    CLOCK_SYNC       = DriverEvent.CLOCK_SYNC
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE  = DriverEvent.STOP_AUTOSAMPLE

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    ACQUIRE_STATUS   = ProtocolEvent.ACQUIRE_STATUS
    ACQUIRE_SAMPLE   = ProtocolEvent.ACQUIRE_SAMPLE
    CLOCK_SYNC       = ProtocolEvent.CLOCK_SYNC
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE  = ProtocolEvent.STOP_AUTOSAMPLE
 
class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    CLOCK = 'clock'

class Prompt(BaseEnum):
    """
    Device i/o prompts.
    """
    CR_NL = NEWLINE

class Command(BaseEnum):
    """
    Instrument command strings
    """
    CLOCK = "#CLOCK"
    D     = "#D"
    FS    = "#FS"
    STAT  = "#STAT"
    GO    = "#GO"
    STOP  = "#STOP"

class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW          = CommonDataParticleType.RAW
    METBK_PARSED = 'metbk_parsed'
    METBK_STATUS = 'metbk_status'
    
###############################################################################
# Data Particles
###############################################################################

class METBK_SampleDataParticleKey(BaseEnum):
    RECORD_LENGTH = 'record_length'
    PACKET_TYPE = 'packet_type'
    METER_TYPE = 'meter_type'
    SERIAL_NUMBER = 'serial_number'
    A_REFERENCE_DARK_COUNTS = 'a_reference_dark_counts'
    PRESSURE_COUNTS = 'pressure_counts'
    A_SIGNAL_DARK_COUNTS = 'a_signal_dark_counts'
    EXTERNAL_TEMP_RAW = 'external_temp_raw'
    INTERNAL_TEMP_RAW = 'internal_temp_raw'
    C_REFERENCE_DARK_COUNTS = 'c_reference_dark_counts'
    C_SIGNAL_DARK_COUNTS = 'c_signal_dark_counts'
    ELAPSED_RUN_TIME = 'elapsed_run_time'
    NUM_WAVELENGTHS = 'num_wavelengths'
    C_REFERENCE_COUNTS = 'c_reference_counts'
    A_REFERENCE_COUNTS = 'a_reference_counts'
    C_SIGNAL_COUNTS = 'c_signal_counts'
    A_SIGNAL_COUNTS = 'a_signal_counts'
    
class METBK_SampleDataParticle(DataParticle):
    _data_particle_type = DataParticleType.METBK_PARSED
        
    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        SAMPLE_DATA_PATTERN = (r'\s+(-*\d+\.\d+)' +     # BPR
                                '\s+(-*\d+\.\d+)' +     # RH %
                                '\s+(-*\d+\.\d+)' +     # RH temp
                                '\s+(-*\d+\.\d+)' +     # LWR
                                '\s+(-*\d+\.\d+)' +     # PRC
                                '\s+(-*\d+\.\d+)' +     # ST
                                '\s+(-*\d+\.\d+)' +     # SC
                                '\s+(-*\d+\.\d+)' +     # SWR
                                '\s+(-*\d+\.\d+)' +     # We
                                '\s+(-*\d+\.\d+)' +     # Wn
                                '.*?'  + NEWLINE)       # throw away batteries
        return re.compile(SAMPLE_DATA_PATTERN)

    def _build_parsed_values(self):
        
        record = self.raw_data
        
        match = METBK_SampleDataParticle.regex_compiled().match(record)
        
        if not match:
            raise SampleException("METBK_SampleDataParticle: No regex match of parsed sample data: [%s]", record)

        result = []
        
        result.append({DataParticleKey.VALUE_ID: METBK_SampleDataParticleKey.PACKET_TYPE,
                       DataParticleKey.VALUE: ord(match.group(2))})

        return result
    
    
class METBK_StatusDataParticleKey(BaseEnum):
    FIRMWARE_VERSION = 'firmware_version'
    FIRMWARE_DATE = 'firmware_date'
    PERSISTOR_CF_SERIAL_NUMBER = 'persistor_cf_serial_number'
    PERSISTOR_CF_BIOS_VERSION = 'persistor_cf_bios_version'
    PERSISTOR_CF_PICODOS_VERSION = 'persistor_cf_picodos_version'
    
class METBK_StatusDataParticle(DataParticle):
    _data_particle_type = DataParticleType.METBK_STATUS
    
    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        STATUS_DATA_PATTERN = (r'.*?Model: (\w+)\r\n' +     
                                'SerNum: (\w+)\r\n'  +     
                                'CfgDat: (\w+)\r\n' +
                                'Firmware: (\w+)\r\n'  +     
                                'RTClock: (\w+)\r\n'  +     
                                'Logging Interval: (\w+)\r\n'  +     
                                'R-interval: (\w+)\r\n'  +     
                                '(\w+)\r\n'  +                     # compact flash info
                                '.*?Sampling GO\r\n')    
        return re.compile(STATUS_DATA_PATTERN, re.DOTALL)

    def _build_parsed_values(self):
        result = []
        
        data_stream = self.raw_data
        
        log.debug("METBK_StatusDataParticle: input = %s" %data_stream)
            
        log.debug("METBK_StatusDataParticle: result = %s" %result)
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

    def get_resource_params(self):
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
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Add build handlers for device commands.
        self._add_build_handler(Command.CLOCK, self._build_simple_command)

        # Add response handlers for device commands.
        self._add_response_handler(Command.CLOCK, self._parse_clock_response)
 
        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()

        self._chunker = StringChunker(Protocol.sieve_function)

        self._add_scheduler_event(ScheduledJob.ACQUIRE_STATUS, ProtocolEvent.ACQUIRE_STATUS)
        self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.CLOCK_SYNC)
        self._add_scheduler_event(ScheduledJob.AUTOSAMPLE, ProtocolEvent.START_AUTOSAMPLE)

        # Start state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples and status
        """
        matchers = []
        return_list = []

        matchers.append(METBK_SampleDataParticle.regex_compiled())
        matchers.append(METBK_StatusDataParticle.regex_compiled())
                    
        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))
                    
        return return_list

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        self._extract_sample(METBK_SampleDataParticle, METBK_SampleDataParticle.regex_compiled(), chunk, timestamp)
        self._extract_sample(METBK_StatusDataParticle, METBK_StatusDataParticle.regex_compiled(), chunk, timestamp)


    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]


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

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can only be AUTOSAMPLE (instrument has no actual command mode).
        @retval (next_state, result), (ProtocolState.COMMAND or
        State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """

        # force to command mode, this instrument has no autosample mode
        next_state = ProtocolState.COMMAND
        result = ResourceAgentState.IDLE

        log.debug("_handler_unknown_discover: state = %s", next_state)
        return (next_state, result)


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

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_command_set(self, *args, **kwargs):
        """
        no writable parameters so does nothing, just implemented to make framework happy
        """

        next_state = None
        result = None
        return (next_state, result)

    def _handler_command_start_direct(self, *args, **kwargs):
        """
        """
        result = None
        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS

        return (next_state, (next_agent_state, result))

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from SBE16.
        @retval (next_state, (next_agent_state, result)) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        next_agent_state = None
        result = None

        result = self._do_cmd_resp(Command.D, *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_command_clock_sync_clock(self, *args, **kwargs):
        """
        sync clock close to a second edge 
        @retval (next_state, result) tuple, (None, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None


        #self._sync_clock(Command.SET, Parameter.DATE_TIME, TIMEOUT, time_format="%d %b %Y %H:%M:%S")

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
        next_state = None
        result = None

        self._do_cmd_direct(data)
                        
        return (next_state, result)

    def _handler_direct_access_stop_direct(self):
        result = None
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Private helpers.
    ########################################################################

    def _wakeup(self, timeout):
        """There is no wakeup sequence for this instrument"""
        pass
    
    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="start autosample")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="stop autosample")
        self._cmd_dict.add(Capability.CLOCK_SYNC, display_name="synchronize clock")
        self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name="acquire status")

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with XR-420 parameters.
        For each parameter key add value formatting function for set commands.
        """
        # The parameter dictionary.
        self._param_dict = ProtocolParameterDict()
        
        # Add parameter handlers to parameter dictionary for instrument configuration parameters.
        self._param_dict.add(Parameter.CLOCK,
                             r'(.*)\r\n', 
                             lambda match : match.group(1),
                             lambda string : str(string),
                             type=ParameterDictType.STRING,
                             display_name="clock",
                             visibility=ParameterDictVisibility.READ_ONLY)

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. 
        """
        
        log.debug("_update_params:")
        # Issue clock command and parse results.  
        # This is the only parameter and it is always changing so don't bother with the 'change' event
        self._do_cmd_resp(Command.CLOCK)

    def _parse_clock_response(self, response, prompt):
        """
        Parse handler for clock command.
        @param response command response string.
        @param prompt prompt following command response.        
        @throws InstrumentProtocolException if clock command misunderstood.
        """
        log.debug("_parse_clock_response: response=%s, prompt=%s" %(response, prompt))
        if prompt not in [Prompt.CR_NL]: 
            raise InstrumentProtocolException('CLOCK command not recognized: %s.' % response)

        if not self._param_dict.update(response):
            raise InstrumentProtocolException('CLOCK command not parsed: %s.' % response)

        return
