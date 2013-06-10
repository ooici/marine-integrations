"""
@package mi.instrument.noaa.iris.ooicore.driver
@file marine-integrations/mi/instrument/noaa/iris/ooicore/driver.py
@author David Everett
@brief Driver for the ooicore
Release notes:

Driver for IRIS TILT on the RSN-BOTPT instrument (v.6)

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
from mi.core.exceptions import SampleException

###
#    Driver Constant Definitions
###

# newline.
NEWLINE = '\x0a'
IRIS_STRING = 'IRIS,'
IRIS_COMMAND_STRING = '*9900XY'
IRIS_DATA_ON = 'C2' # turns on continuous data
IRIS_DATA_OFF = 'C-OFF' # turns off continuous data
IRIS_DUMP1 = '-DUMP_SETTINGS' # outputs current settings
IRIS_DUMP2 = '-DUMP2' # outputs current extended settings

# default timeout.
TIMEOUT = 10

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
    """
    Currently none
    """

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

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    
class Parameter(DriverParameter):
    """
    Device specific parameters.
    """

class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """

class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    DATA_ON  = IRIS_STRING + IRIS_COMMAND_STRING + IRIS_DATA_ON + NEWLINE # turns on continuous data 
    DATA_OFF = IRIS_STRING + IRIS_COMMAND_STRING + IRIS_DATA_OFF + NEWLINE  # turns off continuous data 
    DUMP_SETTINGS_01  = IRIS_STRING + IRIS_COMMAND_STRING + IRIS_DUMP1 + NEWLINE   # outputs current settings 
    DUMP_SETTINGS_02  = IRIS_STRING + IRIS_COMMAND_STRING + IRIS_DUMP2 + NEWLINE    # outputs current extended settings 

class IRISCommandResponse():

    def __init__(self, raw_data):
        """ 
        Construct a IRISCommandResponse object 
        
        @param raw_data The raw data used in the particle
        """
        self.raw_data = raw_data
        self.iris_command_response = None

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'IRIS,' # pattern starts with IRIS '
        pattern += r'(.*),' # group 1: time
        pattern += r'\*9900XY' # generic part of IRIS command
        pattern += r'(.*)' # group 2: echoed command
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(IRISCommandResponse.regex())

    def check_data_on_off_response(self, expected_response):
        """
        Generic command response method; the expected response
        is passed in as a parameter; that is used to check 
        whether the response from the sensor is valid (positive)
        or not.
        """
        retValue = False

        match = IRISCommandResponse.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of command response: [%s]" %
                                  self.raw_data)
        try:
            resp_time = match.group(1)
            timestamp = time.strptime(resp_time, "%Y/%m/%d %H:%M:%S")
            self.iris_command_response = match.group(2)
            if self.iris_command_response == expected_response:
                retValue = True  

        except ValueError:
            raise SampleException("check_data_on_off_response: ValueError" +
                                  " while converting data: [%s]" %
                                  self.raw_data)
        
        return retValue

class DataParticleType(BaseEnum):
    IRIS_PARSED = 'botpt_iris_sample'

class IRISDataParticleKey(BaseEnum):
    TIME = "iris_time"
    X_TILT = "iris_x_tilt"
    Y_TILT = "iris_y_tilt"
    TEMP = "temperature"
    SN = "serial_number"

class IRISDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Sample:
       IRIS,2013/05/29 00:25:36, -0.0885, -0.7517,28.49,N8642
       IRIS,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642       
    Format:
       IIII,YYYY/MM/DD hh:mm:ss,x.xxxx,y.yyyy,tt.tt,sn

        ID = IIII = IRIS
        Year = YYYY
        Month = MM
        Day = DD
        Hour = hh
        Minutes = mm
        Seconds = ss
        NOTE: The above time expression is all grouped into one string.
        X_TILT = x.xxxx (float degrees)
        Y_TILT = y.yyyy (float degrees)
        Temp = tt.tt (float degrees C)
        Serial Number = sn
    """
    _data_particle_type = DataParticleType.IRIS_PARSED

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'IRIS,' # pattern starts with IRIS '
        pattern += r'(.*),' # 1 time
        pattern += r'( -*[.0-9]+),' # 2 x-tilt
        pattern += r'( -*[.0-9]+),' # 3 y-tilt
        pattern += r'(.*),' # 4 temp
        pattern += r'(.*)' # 5 serial number
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(IRISDataParticle.regex())

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = IRISDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)
            
        try:
            iris_time = match.group(1)
            timestamp = time.strptime(iris_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))
            x_tilt = float(match.group(2))
            y_tilt = float(match.group(3))
            temperature = float(match.group(4))
            sn = str(match.group(5))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)
        
        result = [
                  {DataParticleKey.VALUE_ID: IRISDataParticleKey.TIME,
                   DataParticleKey.VALUE: ntp_timestamp},
                  {DataParticleKey.VALUE_ID: IRISDataParticleKey.X_TILT,
                   DataParticleKey.VALUE: x_tilt},
                  {DataParticleKey.VALUE_ID: IRISDataParticleKey.Y_TILT,
                   DataParticleKey.VALUE: y_tilt},
                  {DataParticleKey.VALUE_ID: IRISDataParticleKey.TEMP,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: IRISDataParticleKey.SN,
                   DataParticleKey.VALUE: sn}
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
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_data_off)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_data_on)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCommand.DATA_ON, self._build_data_on_command)
        self._add_build_handler(InstrumentCommand.DATA_OFF, self._build_data_off_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCommand.DATA_ON, self._parse_data_on_off_resp)
        self._add_response_handler(InstrumentCommand.DATA_OFF, self._parse_data_on_off_resp)

        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        #
        self._chunker = StringChunker(Protocol.sieve_function)


    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        matchers = []
        return_list = []

        matchers.append(IRISDataParticle.regex_compiled())
        matchers.append(IRISCommandResponse.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    def _build_cmd_dict(self):
        """
        Populate the command dictionary with NOAA IRIS Driver metadata information. 
        Currently IRIS only supports DATA_ON and DATA_OFF.
        """
        self._cmd_dict = ProtocolCommandDict()
        
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        pass

    def add_to_buffer(self, data):
        '''
        Overridden because most of the data coming to this driver
        isn't meant for it.  I'm only adding to the buffer when
        a chunk arrives (see my_add_to_buffer, below), so this 
        method does nothing.
        
        @param data: bytes to add to the buffer
        '''
        pass
    
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

        log.debug("_got_chunk_: %s", chunk)
        
        regex = IRISCommandResponse.regex_compiled()
        if regex.match(chunk):
            self._my_add_to_buffer(chunk)
        else:
            if not self._extract_sample(IRISDataParticle, 
                                        IRISDataParticle.regex_compiled(), 
                                        chunk, timestamp):
                raise InstrumentProtocolException("Unhandled chunk")


    def _build_data_on_command(self, cmd, *args, **kwargs):
        return cmd + NEWLINE

    def _build_data_off_command(self, cmd, *args, **kwargs):
        return cmd + NEWLINE

    def _parse_data_on_off_resp(self, response, prompt):
        log.debug("_parse_data_on_off_resp: response: %r; prompt: %s", response, prompt)
        return response.iris_command_response
        
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
        
        response = None
        regex = IRISCommandResponse.regex_compiled()
        
        """
        Spin around for <timeout> looking for the response to arrive
        """
        continuing = True
        while continuing:
            if regex.match(self._promptbuf):
                response = IRISCommandResponse(self._promptbuf)
                if response.check_data_on_off_response(expected_prompt):
                    continuing = False
            else:
                self._promptbuf = ''
                time.sleep(.1)

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException("in BOTPT IRIS driver._get_response()")

        return ('IRIS_RESPONSE', response)
    
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

    def _handler_autosample_data_off(self):
        """
        """
        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        result = self._do_cmd_resp(InstrumentCommand.DATA_OFF, 
                                   expected_prompt = IRIS_DATA_OFF)
        
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

        next_state = None
        result = {}

        return (next_state, result)

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """
        next_state = None
        result = None

        params = args[0]
        
        return (next_state, result)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        """
        result = None
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return (next_state, (next_agent_state, result))

    """
    DHE TODO: make this be for the iris data on command
    """
    def _handler_command_data_on(self, *args, **kwargs):
        """
        Turn the iris on
        """
        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        """ 
        call _do_cmd_resp, passing our iris_duration parameter as the expected_prompt
        """
        result = self._do_cmd_resp(InstrumentCommand.DATA_ON, 
                                   expected_prompt = IRIS_DATA_ON)

        return (next_state, (next_agent_state, result))

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
