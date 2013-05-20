"""
@package mi.instrument.noaa.heat.ooicore.driver
@file marine-integrations/mi/instrument/noaa/heat/ooicore/driver.py
@author David Everett
@brief Driver for the ooicore
Release notes:

Driver for LILY HEATER on the RSN-BOTPT instrument (v.6)

"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import string
import re
import time
import datetime
import ntplib

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException

###
#    Driver Constant Definitions
###

# newline.
NEWLINE = '\x0d\x0a'

# default timeout.
TIMEOUT = 10

OFF_HEAT_DURATION = 0
DEFAULT_HEAT_DURATION = 2

class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW

class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE

class ExportedInstrumentCommand(BaseEnum):
    HEAT_ON = "EXPORTED_INSTRUMENT_CMD_HEAT_ON"
    HEAT_OFF = "EXPORTED_INSTRUMENT_CMD_HEAT_OFF"

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
    HEAT_ON = ExportedInstrumentCommand.HEAT_ON
    HEAT_OFF = ExportedInstrumentCommand.HEAT_OFF

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    HEAT_ON = ProtocolEvent.HEAT_ON
    HEAT_OFF = ProtocolEvent.HEAT_OFF
    
class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    HEAT_DURATION = "heat_duration"

class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """

class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    HEAT_ON  = 'HEAT,'    # turns the heater on; HEAT,<number of hours> 
    HEAT_OFF = 'HEAT,0'   # turns the heater off

class HEATCommandResponse():

    def __init__(self, raw_data):
        """ 
        Construct a HEATCommandResponse object 
        
        @param raw_data The raw data used in the particle
        """
        self.raw_data = raw_data

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'HEAT,' # pattern starts with HEAT '
        pattern += r'(.*),' # 1 time
        pattern += r'\*([0-9])' # echoed command
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(HEATCommandResponse.regex())

    def check_heat_on_off_response(self, heat_duration_value):
        """
        """
        retValue = False
        
        match = HEATCommandResponse.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of command response: [%s]" %
                                  self.raw_data)
            
        try:
            heat_time = match.group(1)
            timestamp = time.strptime(heat_time, "%Y/%m/%d %H:%M:%S")
            #if heat_duration_value == int(match.group(2)):
            rx_heat_duration_value = match.group(2)
            if heat_duration_value == rx_heat_duration_value:
                retValue = True
            else:
                log.error("BOTPT HEAT Responded with: %s; expected %s",
                          rx_heat_duration_value, heat_duration_value)

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)
        
        return retValue

class DataParticleType(BaseEnum):
    HEAT_PARSED = 'botpt_heat_sample'

class HEATDataParticleKey(BaseEnum):
    TIME = "heat_time"
    X_TILT = "heat_x_tilt"
    Y_TILT = "heat_y_tilt"
    TEMP = "temperature"

class HEATDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Sample:
       HEAT,2013/04/23 18:24:46,0000,0001,0025
       HEAT,2013/04/19 22:54:11,001,0001,0025
    Format:
       IIII,YYYY/MM/DD hh:mm:ss,xxxx,yyyy,tttt

        ID = IIII = HEAT
        Year = YYYY
        Month = MM
        Day = DD
        Hour = hh
        Minutes = mm
        Seconds = ss
        NOTE: The above time expression is all grouped into one string.
        X_TILT = xxxx (integer degrees)
        Y_TILT = yyyy (integer degrees)
        Temp = tttt (integer degrees C)
    """
    _data_particle_type = DataParticleType.HEAT_PARSED

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'HEAT,' # pattern starts with HEAT '
        pattern += r'(.*),' # 1 time
        pattern += r'(-*[0-9]+),' # 2 x-tilt
        pattern += r'(-*[0-9]+),' # 3 y-tilt
        pattern += r'([0-9]{4})' # 4 temp
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(HEATDataParticle.regex())

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = HEATDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)
            
        try:
            heat_time = match.group(1)
            timestamp = time.strptime(heat_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))
            x_tilt = int(match.group(2))
            y_tilt = int(match.group(3))
            temperature = int(match.group(4))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)
        
        result = [
                  {DataParticleKey.VALUE_ID: HEATDataParticleKey.TIME,
                   DataParticleKey.VALUE: ntp_timestamp},
                  {DataParticleKey.VALUE_ID: HEATDataParticleKey.X_TILT,
                   DataParticleKey.VALUE: x_tilt},
                  {DataParticleKey.VALUE_ID: HEATDataParticleKey.Y_TILT,
                   DataParticleKey.VALUE: y_tilt},
                  {DataParticleKey.VALUE_ID: HEATDataParticleKey.TEMP,
                   DataParticleKey.VALUE: temperature}
                  ]
        
        return result

###############################################################################
# Data Particles
###############################################################################


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

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.HEAT_ON, self._handler_command_heat_on)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.HEAT_OFF, self._handler_command_heat_off)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCommand.HEAT_ON, self._build_heat_on_command)
        self._add_build_handler(InstrumentCommand.HEAT_OFF, self._build_heat_off_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCommand.HEAT_ON, self._parse_heat_on_response)

        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        #
        self._chunker = StringChunker(Protocol.sieve_function)

        self._heat_duration = DEFAULT_HEAT_DURATION


    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        matchers = []
        return_list = []

        matchers.append(HEATDataParticle.regex_compiled())
        matchers.append(HEATCommandResponse.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _build_cmd_dict(self):
        """
        Populate the command dictionary with NOAA HEAT Driver metadata information. 
        Currently HEAT only supports HEAT_ON and HEAT_OFF.
        """
        self._cmd_dict = ProtocolCommandDict()
        
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.


        # Next 2 work together to pull 2 values out of a single line.
        #

        self._param_dict.add(Parameter.HEAT_DURATION,
            r'Not used. This is just to satisfy the param_dict',
            None,
            None,
            type=ParameterDictType.INT,
            display_name="Heat Duration",
            multi_match=False,
            visibility=ParameterDictVisibility.READ_WRITE)

    def _extract_command_response(self, particle_class, regex, line):
        """
        Extract sample from a response line if present and publish
        parsed particle

        @param particle_class The class to instantiate for this specific
            data particle. Parameterizing this allows for simple, standard
            behavior from this routine
        @param regex The regular expression that matches a data sample
        @param line string to match for sample.

        @retval dict of dicts {'parsed': parsed_sample, 'raw': raw_sample} if
                the line can be parsed for a sample. Otherwise, None.
        @todo Figure out how the agent wants the results for a single poll
            and return them that way from here
        """
        parsed_response = None
        if regex.match(line):
        
            particle = particle_class(line)
            parsed_response = particle.check_heat_on_off_response()

        return parsed_response

    def add_to_buffer(self, data):
        '''
        Overridden because most of the data coming to this driver
        isn't meant for it.  I'm only adding to the buffer when
        a chunk arrives, so this method does nothing.
        
        @param data: bytes to add to the buffer
        '''
        # Update the line and prompt buffers.
        #self._linebuf += data
        #self._promptbuf += data
        #self._last_data_timestamp = time.time()

    def _my_add_to_buffer(self, data):
        """
        Replaces add_to_buffer. Most data coming to this driver isn't meant
        for it.  I'm only adding to the buffer when data meant for this 
        driver arrives.  That is accomplished using the chunker mechanism. This
        method would normally collet any data fragments that are then search by
        the get_response method in the context of a synchronous command sent
        from the observatory.  However, because so much data arrives here that
        is not applicable, the add_to_buffer method has been overridden to do
        nothing.
        
        @param data: bytes to add to the buffer
        """
        
        # Update the line and prompt buffers.
        self._linebuf += data
        self._promptbuf += data
        self._last_data_timestamp = time.time()

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Invoke
        this driver's _my_add_to_buffer, and then pass it to extract_sample
        with the appropriate particle objects and REGEXes.  We need to invoke
        _my_add_to_buffer, because we've overridden the base class
        add_to_buffer that is called from got_data().  The reason is explained
        in comments in _my_add_to_buffer.
        """
        
        self._my_add_to_buffer(chunk)
        
        """
        Invoke _extract_sample here.  However, don't raise an exception if 
        if _extract_sample does not fine one, because this this driver only 
        deals in chunks; that is, all data that is pertinent to this driver
        has been defined as a particle.  (We can get chunks that won't apply
        to _extract_sample.)
        """
        self._extract_sample(HEATDataParticle, HEATDataParticle.regex_compiled(), chunk, timestamp)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

    def _build_heat_on_command(self, cmd, *args, **kwargs):
        return cmd + str(self._heat_duration) + NEWLINE

    def _build_heat_off_command(self, cmd, *args, **kwargs):
        return cmd + NEWLINE

    def _parse_heat_on_response(self, response, prompt):
        log.debug("_parse_heat_on_response: response: %s; prompt: %s", response, prompt)
        
    def _wakeup(self, timeout, delay=1):
        """
        Overriding _wakeup; does not apply to this instrument
        """
        pass

    def _get_response(self, timeout=10, expected_prompt=None):
        """
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolExecption on timeout
        """
        # Grab time for timeout and wait for response

        starttime = time.time()
        #self._extract_command_response(HEATCommandResponse, HEATCommandResponse.regex_compiled(), chunk))):
        
        response = None
        regex = HEATCommandResponse.regex_compiled()
        
        """
        Spin around for <timeout> looking for the response to arrive
        """
        continuing = True
        while continuing:
            if regex.match(self._promptbuf):
                response = HEATCommandResponse(self._promptbuf)
                if response.check_heat_on_off_response(expected_prompt):
                    continuing = False
                else:
                    raise InstrumentProtocolException("in BOTPT HEAT driver._get_response()")
            else:
                time.sleep(.1)

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in BOTPT HEAT driver._get_response()")

        return ('HEAT_RESPONSE', response)
    
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
        Discover current state
        @retval (next_state, result)
        """
        return (ProtocolState.COMMAND, ResourceAgentState.IDLE)

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_autosample_stop_autosample(self):
        """
        """
        result = None
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND
        
        return (next_state, (next_agent_state, result))

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.
        #self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """
        # DHE TEMPTEMP
        log.error(" ------------------------> DHE _handler_command_get!! args: %r, kwargs: %r", args, kwargs)
        
        next_state = None
        result = {}
        result[Parameter.HEAT_DURATION] = self._heat_duration


        return (next_state, result)

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """
        next_state = None
        result = None

        # DHE TEMPTEMP
        log.error(" ------------------------> DHE _handler_command_set!! args: %r, kwargs: %r", args, kwargs)
        
        params = args[0]
        new_heat_duration = params[Parameter.HEAT_DURATION]
        if new_heat_duration != self._heat_duration:
            log.info("BOTPT HEAT Driver: setting heat duration from %d to %d", self._heat_duration, new_heat_duration)
            self._heat_duration = new_heat_duration 
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        else:
            log.info("BOTPT HEAT Driver: heat duration already %d; not changing.", new_heat_duration)
        
        return (next_state, result)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        """
        result = None
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return (next_state, (next_agent_state, result))

    def _handler_command_heat_on(self, *args, **kwargs):
        """
        Turn the heater on
        """
        next_state = None
        result = None

        # DHE TEMPTEMP
        log.error(" ------------------------> DHE _handler_command_heat_on!! args: %r, kwargs: %r", args, kwargs)

        # Issue heat_on command.
        expected_response = '*' + str(self._heat_duration)
        
        """ 
        call _do_cmd_resp, passing our heat_duration parameter as the expected_prompt
        """
        result = self._do_cmd_resp(InstrumentCommand.HEAT_ON, expected_prompt = str(self._heat_duration))
        #self._connection.send(InstrumentCommand.HEAT_ON)                
        return (next_state, result)

    def _handler_command_heat_off(self, *args, **kwargs):
        """
        Turn the heater off
        """
        next_state = None
        result = None

        # DHE TEMPTEMP
        log.error(" ------------------------> DHE _handler_command_heat_off!! args: %r, kwargs: %r", args, kwargs)
                
        """ 
        call _do_cmd_resp, passing our heat_duration parameter as the expected_prompt
        """
        result = self._do_cmd_resp(InstrumentCommand.HEAT_OFF, expected_prompt = str(OFF_HEAT_DURATION))
        return (next_state, result)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

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
