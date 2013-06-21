"""
@package mi.instrument.mclane.ras.ooicore.driver
@file marine-integrations/mi/instrument/mclane/ras/ooicore/driver.py
@author Bill Bollenbacher
@brief Driver for the rasfl
Release notes:

initial version
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

import re
import time
import string
import json

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, \
                               InstrumentProtocolException, \
                               InstrumentTimeoutException

from mi.core.time import get_timestamp_delayed
                               
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverConnectionState

from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType

from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import DriverConfigKey

from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType

from mi.core.instrument.driver_dict import DriverDictKey

from mi.core.instrument.protocol_param_dict import ProtocolParameterDict, \
                                                   ParameterDictType, \
                                                   ParameterDictVisibility


NEWLINE = '\r\n'
CONTROL_C = '\x03'

# default timeout.
TIMEOUT = 10
INTER_CHARACTER_DELAY = .2

####
#    Driver Constant Definitions
####

class ScheduledJob(BaseEnum):
    CLOCK_SYNC = 'clock_sync'

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
    CLOCK_SYNC       = DriverEvent.CLOCK_SYNC

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET              = ProtocolEvent.GET
    CLOCK_SYNC       = ProtocolEvent.CLOCK_SYNC
 
class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    BATTERY = 'battery'
    SAMPLE_INTERVAL = 'sample_interval'

class Prompt(BaseEnum):
    """
    Device i/o prompts.
    """
    PERIOD               = '.'
    SUSPENDED            = 'Suspended ... '
    ENTER_CTRL_C         = 'Enter ^C now to wake up ...'
    UNRECOGNIZED_CMD     = '] unrecognized command'
    COMMAND_INPUT        = '>'
    UNRECOGNIZED_COMMAND = 'unrecognized command'

class Command(BaseEnum):
    """
    Instrument command strings
    """
    END_OF_LINE = NEWLINE
    CONTROL_C = CONTROL_C
    BATTERY = 'battery'

class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW          = CommonDataParticleType.RAW
    RASFL_PARSED = 'rasfl_parsed'
    
###############################################################################
# Data Particles
###############################################################################

class RASFL_SampleDataParticleKey(BaseEnum):
    BAROMETRIC_PRESSURE = 'barometric_pressure'
    RELATIVE_HUMIDITY = 'relative_humidity'
    AIR_TEMPERATURE = 'air_temperature'
    LONGWAVE_IRRADIANCE = 'longwave_irradiance'
    PRECIPITATION = 'precipitation'
    SEA_SURFACE_TEMPERATURE = 'sea_surface_temperature'
    SEA_SURFACE_CONDUCTIVITY = 'sea_surface_conductivity'
    SHORTWAVE_IRRADIANCE = 'shortwave_irradiance'
    EASTWARD_WIND_VELOCITY = 'eastward_wind_velocity'
    NORTHWARD_WIND_VELOCITY = 'northward_wind_velocity'
    
class RASFL_SampleDataParticle(DataParticle):
    _data_particle_type = DataParticleType.RASFL_PARSED
        
    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        SAMPLE_DATA_PATTERN = (r'(-*\d+\.\d+)' +        # BPR
                                '\s*(-*\d+\.\d+)' +     # RH %
                                '\s*(-*\d+\.\d+)' +     # RH temp
                                '\s*(-*\d+\.\d+)' +     # LWR
                                '\s*(-*\d+\.\d+)' +     # PRC
                                '\s*(-*\d+\.\d+)' +     # ST
                                '\s*(-*\d+\.\d+)' +     # SC
                                '\s*(-*\d+\.\d+)' +     # SWR
                                '\s*(-*\d+\.\d+)' +     # We
                                '\s*(-*\d+\.\d+)' +     # Wn
                                '.*?' + NEWLINE)        # throw away batteries
        return re.compile(SAMPLE_DATA_PATTERN, re.DOTALL)

    def _build_parsed_values(self):
        
        match = RASFL_SampleDataParticle.regex_compiled().match(self.raw_data)
        
        if not match:
            raise SampleException("RASFL_SampleDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        
        result = [{DataParticleKey.VALUE_ID: RASFL_SampleDataParticleKey.BAROMETRIC_PRESSURE,
                   DataParticleKey.VALUE: float(match.group(1))},
                  {DataParticleKey.VALUE_ID: RASFL_SampleDataParticleKey.RELATIVE_HUMIDITY,
                   DataParticleKey.VALUE: float(match.group(2))},
                  {DataParticleKey.VALUE_ID: RASFL_SampleDataParticleKey.AIR_TEMPERATURE,
                   DataParticleKey.VALUE: float(match.group(3))},
                  {DataParticleKey.VALUE_ID: RASFL_SampleDataParticleKey.LONGWAVE_IRRADIANCE,
                   DataParticleKey.VALUE: float(match.group(4))},
                  {DataParticleKey.VALUE_ID: RASFL_SampleDataParticleKey.PRECIPITATION,
                   DataParticleKey.VALUE: float(match.group(5))},
                  {DataParticleKey.VALUE_ID: RASFL_SampleDataParticleKey.SEA_SURFACE_TEMPERATURE,
                   DataParticleKey.VALUE: float(match.group(6))},
                  {DataParticleKey.VALUE_ID: RASFL_SampleDataParticleKey.SEA_SURFACE_CONDUCTIVITY,
                   DataParticleKey.VALUE: float(match.group(7))},
                  {DataParticleKey.VALUE_ID: RASFL_SampleDataParticleKey.SHORTWAVE_IRRADIANCE,
                   DataParticleKey.VALUE: float(match.group(8))},
                  {DataParticleKey.VALUE_ID: RASFL_SampleDataParticleKey.EASTWARD_WIND_VELOCITY,
                   DataParticleKey.VALUE: float(match.group(9))},
                  {DataParticleKey.VALUE_ID: RASFL_SampleDataParticleKey.NORTHWARD_WIND_VELOCITY,
                   DataParticleKey.VALUE: float(match.group(10))}]
        
        log.debug("METBK_SampleDataParticle._build_parsed_values: result=%s" %result)
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
        self._protocol_fsm = ThreadSafeFSM(ProtocolState, ProtocolEvent, ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_sync_clock)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Add build handlers for device commands.
        self._add_build_handler(Command.BATTERY, self._build_simple_command)

        # Add response handlers for device commands.
        self._add_response_handler(Command.BATTERY, self._parse_battery_response)
 
        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()
        
        self._chunker = StringChunker(Protocol.sieve_function)

        self._add_scheduler_event(ScheduledJob.CLOCK_SYNC, ProtocolEvent.CLOCK_SYNC)

        # Start state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples and status
        """
        matchers = []
        return_list = []

        matchers.append(RASFL_SampleDataParticle.regex_compiled())
                    
        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))
                    
        """
        if return_list != []:
            log.debug("sieve_function: raw_data=%s, return_list=%s" %(raw_data, return_list))
        """
        return return_list

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        log.debug("_got_chunk: chunk=%s" %chunk)
        self._extract_sample(RASFL_SampleDataParticle, RASFL_SampleDataParticle.regex_compiled(), chunk, timestamp)

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
        Apply sample_interval startup parameter.  
        """

        config = self.get_startup_config()
        log.debug("apply_startup_params: startup config = %s" %config)
        if config.has_key(Parameter.SAMPLE_INTERVAL):
            log.debug("apply_startup_params: setting sample_interval to %d" %config[Parameter.SAMPLE_INTERVAL])
            self._param_dict.set_value(Parameter.SAMPLE_INTERVAL, config[Parameter.SAMPLE_INTERVAL])

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
        Discover current state; can only be COMMAND (instrument has no actual AUTOSAMPLE mode).
        @retval (next_state, result), (ProtocolState.COMMAND, None) if successful.
        """

        # force to command mode, this instrument has no autosample mode
        next_state = ProtocolState.COMMAND
        result = ResourceAgentState.COMMAND

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
    # general handlers.
    ########################################################################

    def _handler_sync_clock(self, *args, **kwargs):
        """
        sync clock close to a second edge 
        @retval (next_state, (next_agent_state, result)) tuple, (None, (None, None)).
        @throws InstrumentTimeoutException if device respond correctly.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None

        time_format = "%Y/%m/%d %H:%M:%S"
        str_val = get_timestamp_delayed(time_format)
        log.debug("Setting instrument clock to '%s'", str_val)
        self._do_cmd_resp(Command.STOP, expected_prompt=Prompt.STOPPED)
        try:
            self._do_cmd_resp(Command.SET_CLOCK, str_val, expected_prompt=Prompt.CR_NL)
        finally:
            # ensure that we try to start the instrument sampling again
            self._do_cmd_resp(Command.GO, expected_prompt=Prompt.GO)

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Private helpers.
    ########################################################################

    def _wakeup(self, wakeup_timeout=10, response_timeout=3):
        """
        Over-ridden because waking this instrument up is a multi-step process with
        two different requests required
        @param wakeup_timeout The timeout to wake the device.
        @param response_timeout The time to look for response to a wakeup attempt.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        sleep_time = .1
        command = Command.END_OF_LINE
        
        # Grab start time for overall wakeup timeout.
        starttime = time.time()
        
        while True:
            # Clear the prompt buffer.
            log.debug("_wakeup: clearing promptbuf: %s" % self._promptbuf)
            self._promptbuf = ''
        
            # Send a command and wait delay amount for response.
            log.debug('_wakeup: Sending command %s, delay=%s' %(command.encode("hex"), response_timeout))
            for char in command:
                self._connection.send(char)
                time.sleep(INTER_CHARACTER_DELAY)
            sleep_amount = 0
            while True:
                time.sleep(sleep_time)
                if self._promptbuf.find(Prompt.COMMAND_INPUT) != -1:
                    # instrument is awake
                    log.debug('_wakeup: got command input prompt %s' % Prompt.COMMAND_INPUT)
                    # add inter-character delay which _do_cmd_resp() incorrectly doesn't add to the start of a transmission
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
                    log.debug("_wakeup: expected response not received, buffer=%s" % self._promptbuf)
                    break

            if time.time() > starttime + wakeup_timeout:
                raise InstrumentTimeoutException("_wakeup(): instrument failed to wakeup in %d seconds time" %wakeup_timeout)

    
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
        self._param_dict.add(Parameter.BATTERY,
                             r'Battery: (.*)V', 
                             lambda match : match.group(1),
                             lambda string : str(string),
                             type=ParameterDictType.STRING,
                             display_name="battery",
                             expiration=0,
                             visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.SAMPLE_INTERVAL,
                             r'Not used. This parameter is not parsed from instrument response',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=30,
                             value=30,
                             startup_param=True,
                             display_name="sample_interval",
                             visibility=ParameterDictVisibility.IMMUTABLE)

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        CommandResponseInstrumentProtocol._do_cmd_resp(self, cmd, args, kwargs, write_delay=INTER_CHARACTER_DELAY)

    
    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. 
        """
        
        log.debug("_update_params:")
        self._do_cmd_resp(Command.BATTERY)

    def _parse_battery_response(self, response, prompt):
        """
        Parse handler for battery command.
        @param response command response string.
        @param prompt prompt following command response.        
        @throws InstrumentProtocolException if clock command misunderstood.
        """
        log.debug("_parse_battery_response: response=%s, prompt=%s" %(response, prompt))
        if prompt == Prompt.UNRECOGNIZED_COMMAND: 
            raise InstrumentProtocolException('battery command not recognized: %s.' % response)

        if not self._param_dict.update(response):
            raise InstrumentProtocolException('battery command not parsed: %s.' % response)

        return

