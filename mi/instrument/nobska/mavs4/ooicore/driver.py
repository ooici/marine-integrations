"""
@package mi.instrument.nobska.mavs4.ooicore.driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4/ooicore/driver.py
@author Bill Bollenbacher
@brief Driver for the mavs4
Release notes:

initial release
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'


import time
import re
import datetime
import copy

from mi.core.common import BaseEnum
from mi.core.time import get_timestamp_delayed
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.instrument.instrument_protocol import MenuInstrumentProtocol
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.exceptions import InstrumentTimeoutException, \
                               InstrumentParameterException, \
                               InstrumentProtocolException, \
                               InstrumentStateException
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictVal
from mi.core.common import InstErrorCode
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue, CommonDataParticleType

from mi.core.log import get_logger
log = get_logger()


class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW

COMMAND = 'command'
RESPONSE = 'response'
NEXT_COMMAND = 'next_comand'

INSTRUMENT_NEWLINE = '\r\n'
WRITE_DELAY = 0

# default timeout.
INSTRUMENT_TIMEOUT = 5

# Device prompts.
class InstrumentPrompts(BaseEnum):
    """
    MAVS-4 prompts.
    The main menu prompt has 2 bells and the sub menu prompts have one; the PicoDOS prompt has none.
    """
    MAIN_MENU     = '\a\b ? \a\b'
    SUB_MENU      = '\a\b'
    PICO_DOS      = 'Enter command >> '
    SLEEPING      = 'Sleeping . . .'
    SLEEP_WAKEUP  = 'Enter <CTRL>-<C> now to wake up?'
    DEPLOY_WAKEUP = '>>> <CTRL>-<C> to terminate deployment <<<'
    SET_DONE      = 'New parameters accepted.'
    SET_FAILED    = 'Invalid entry'
    SET_TIME      = '] ? \a\b'
    GET_TIME      = 'Enter correct time ['
    CHANGE_TIME   = 'Change time & date (Yes/No) [N] ?\a\b'
    NOTE_INPUT    = '> '
    DEPLOY_MENU   = 'G| Go (<CTRL>-<G> skips checks)\r\n\r\n'
    
class InstrumentCmds(BaseEnum):
    CONTROL_C     = '\x03'   # CTRL-C (end of text)
    DEPLOY_GO     = '\a'     # CTRL-G (bell)
    SET_TIME      = '1'
    ENTER_TIME    = 'enter_time'
    ANSWER_YES    = 'y'
    DEPLOY_MENU   = '6'
    SET_NOTE      = 'set_note'
    ENTER_NOTE    = 'enter_note'

class ProtocolStates(BaseEnum):
    """
    Protocol states for MAVS-4. Cherry picked from DriverProtocolState enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    TEST = DriverProtocolState.TEST
    CALIBRATE = DriverProtocolState.CALIBRATE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    
class ProtocolEvent(BaseEnum):
    """
    Protocol events for MAVS-4. Cherry picked from DriverEvent enum.
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC

class Capability(BaseEnum):
    """
    Capabilities that are exposed to the user (subset of above)
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC

# Device specific parameters.
class InstrumentParameters(DriverParameter):
    """
    Device parameters for MAVS-4.
    """
    SYS_CLOCK = 'sys_clock'
    NOTE1 = 'note1'
    NOTE2 = 'note2'
    NOTE3 = 'note3'
    VELOCITY_FRAME = 'velocity_frame'
    MONITOR = 'monitor'
    QUERY_MODE = 'query_mode'
    MEASUREMENT_FREQUENCY = 'measurement_frequency'
    MEASUREMENTS_PER_SAMPLE = 'measurements_per_sample'
    SAMPLE_PERIOD = 'sample_period'
    SAMPLES_PER_BURST = 'samples_per_burst'
    BURST_INTERVAL = 'bursts_interval'
    
class DeployMenuParameters(BaseEnum):
    NOTE1 = InstrumentParameters.NOTE1
    NOTE2 = InstrumentParameters.NOTE2
    NOTE3 = InstrumentParameters.NOTE3

class SubMenues(BaseEnum):
    ROOT        = 'root_menu'
    SET_TIME    = 'set_time'
    FLASH_CARD  = 'flash_card'
    CALIBRATION = 'calibration'
    SLEEP       = 'sleep'
    BENCH_TESTS = 'bench_tests'
    DEPLOY      = 'deploy'
    OFFLOAD     = 'offload'
    PICO_DOS    = 'pico_dos'
    DUMMY       = 'dummy'

class MultilineParameterDictVal(ParameterDictVal):
    
    def __init__(self, name, pattern, f_getval, f_format, value=None,
                 visibility=ParameterDictVisibility.READ_WRITE,
                 menu_path_read=None,
                 submenu_read=None,
                 menu_path_write=None,
                 submenu_write=None,                 
                 multi_match=False,
                 direct_access=False,
                 startup_param=True,
                 default_value=None,
                 init_value=None):
        """
        Parameter value constructor.
        @param name The parameter name.
        @param pattern The regex that matches the parameter in line output.
        @param f_getval The fuction that extracts the value from a regex match.
        @param f_format The function that formats the parameter value for a set command.
        @param visibility The ParameterDictVisibility value that indicates what
        the access to this parameter is
        @param menu_path The path of menu options required to get to the parameter
        value display when presented in a menu-based instrument
        @param value The parameter value (initializes to None).
        """
        self.name = name
        self.pattern = pattern
        #log.debug('BinaryParameterDictVal.__int__(); pattern=%s' %pattern)
        self.regex = re.compile(pattern, re.DOTALL)
        self.f_getval = f_getval
        self.f_format = f_format
        self.value = value
        self.menu_path_read = menu_path_read
        self.submenu_read = submenu_read
        self.menu_path_write = menu_path_write
        self.submenu_write = submenu_write
        self.visibility = visibility
        self.multi_match = multi_match
        self.direct_access = direct_access
        self.startup_param = startup_param
        self.default_value = default_value
        self.init_value = init_value        

    def update(self, input):
        """
        Attempt to udpate a parameter value. If the input string matches the
        value regex, extract and update the dictionary value.
        @param input A string possibly containing the parameter value.
        @retval True if an update was successful, False otherwise.
        """
        match = self.regex.search(input)
        #log.debug("MultilineParameterDictVal.update: match=<%s> input=<%s>" %(match.group(0), input))
        if match:
            self.value = self.f_getval(match)
            log.debug('MultilineParameterDictVal.update: Updated parameter %s=<%s>', self.name, str(self.value))
            return True
        else:
            return False

class Mavs4ProtocolParameterDict(ProtocolParameterDict):
    
    def add(self, name, pattern, f_getval, f_format, value=None,
            visibility=ParameterDictVisibility.READ_WRITE,
            menu_path_read=None, submenu_read=None,
            menu_path_write=None, submenu_write=None,
            multi_match=False, direct_access=False, startup_param=True,
            default_value=None, init_value=None):
        """
        Add a parameter object to the dictionary.
        @param name The parameter name.
        @param pattern The regex that matches the parameter in line output.
        @param f_getval The function that extracts the value from a regex match.
        @param f_format The function that formats the parameter value for a set command.
        @param visibility The ParameterDictVisibility value that indicates what
        the access to this parameter is
        @param menu_path The path of menu options required to get to the parameter
        value display when presented in a menu-based instrument
        @param direct_access T/F for tagging this as a direct access parameter
        to be saved and restored in and out of direct access
        @param startup_param T/F for tagging this as a startup parameter to be
        applied when the instrument is first configured
        @param default_value The default value to use for this parameter when
        a value is needed, but no other instructions have been provided.
        @param init_value The value that a parameter should be set to during
        initialization or re-initialization
        @param value The parameter value (initializes to None).        
        """
        val = MultilineParameterDictVal(name, pattern, f_getval, f_format,
                                        value=value,
                                        visibility=visibility,
                                        menu_path_read=menu_path_read,
                                        submenu_read=submenu_read,
                                        menu_path_write=menu_path_write,
                                        submenu_write=submenu_write,
                                        multi_match=multi_match,
                                        direct_access=direct_access,
                                        startup_param=startup_param,
                                        default_value=default_value,
                                        init_value=init_value)
        self._param_dict[name] = val
        
    def set_from_string(self, name, line):
        """
        Set a parameter value in the dictionary.
        @param name The parameter name.
        @param line The parameter value as a string.
        @raises KeyError if the name is invalid.
        """
        log.debug("Mavs4ProtocolParameterDict.set_from_string(): name=%s, line=%s" %(name, line))
        try:
            param = self._param_dict[name]
        except:
            return
        param.value = param.f_getval(line)

    def set_from_value(self, name, value):
        """
        Set a parameter value in the dictionary.
        @param name The parameter name.
        @param value The parameter value.
        @raises KeyError if the name is invalid.
        """
        log.debug("Mavs4ProtocolParameterDict.set_from_value(): name=%s, value=%s" %(name, value))
        self._param_dict[name].value = value
        
    def format_parameter(self, name):
        """
        Format the parameter for a set command.
        @param name The name of the parameter.
        @retval The value formatted as a string for writing to the device.
        @raises InstrumentProtocolException if the value could not be formatted.
        @raises KeyError if the parameter name is invalid.
        """
        return self._param_dict[name].f_format(self._param_dict[name].value)
    
    def update(self, name, response):
        #log.debug('Mavs4ProtocolParameterDict.update(): set %s from %s' %(name, response))
        return self._param_dict[name].update(response)

###
#   Driver for mavs4
###
class mavs4InstrumentDriver(SingleConnectionInstrumentDriver):

    """
    Instrument driver class for MAVS-4 driver.
    Uses CommandResponseInstrumentProtocol to communicate with the device
    """

    def __init__(self, evt_callback):
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)
    
    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = mavs4InstrumentProtocol(InstrumentPrompts, INSTRUMENT_NEWLINE, self._driver_event)
        
###
#   Protocol for mavs4
###
class mavs4InstrumentProtocol(MenuInstrumentProtocol):
    """
    The protocol is a very simple command/response protocol with a few show
    commands and a few set commands.
    """
    
    def __init__(self, prompts, newline, driver_event):
        """
        """
        self.write_delay = WRITE_DELAY
        self._last_data_timestamp = None
        self.eoln = INSTRUMENT_NEWLINE
        
        # create short alias for Directions class
        Directions = MenuInstrumentProtocol.MenuTree.Directions
        
        # create MenuTree object
        menu = MenuInstrumentProtocol.MenuTree({
            SubMenues.ROOT       : [],
            SubMenues.SET_TIME   : [Directions(InstrumentCmds.SET_TIME, InstrumentPrompts.SET_TIME)],
            SubMenues.DEPLOY     : [Directions(InstrumentCmds.DEPLOY_MENU, InstrumentPrompts.DEPLOY_MENU, 20)]
            })
        
        MenuInstrumentProtocol.__init__(self, menu, prompts, newline, driver_event)
                
        self._protocol_fsm = InstrumentFSM(ProtocolStates, 
                                           ProtocolEvent, 
                                           ProtocolEvent.ENTER,
                                           ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolStates.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolStates.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolStates.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.GET, self._handler_get)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvent.CLOCK_SYNC, self._handler_command_clock_sync)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Set state machine in UNKNOWN state. 
        self._protocol_fsm.start(ProtocolStates.UNKNOWN)

        self._build_command_handlers()
 
        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # create chunker for processing instrument samples.
        self._chunker = StringChunker(mavs4InstrumentProtocol.chunker_sieve_function)


    @staticmethod
    def chunker_sieve_function(raw_data):
        """ The method that detects data sample structures from instrument
        """
        return_list = []
        
        """
        for structure_sync, structure_len in sample_structures:
            start = raw_data.find(structure_sync)
            if start != -1:    # found a sync pattern
                if start+structure_len <= len(raw_data):    # only check the CRC if all of the structure has arrived
                    calculated_checksum = BinaryProtocolParameterDict.calculate_checksum(raw_data[start:start+structure_len], structure_len)
                    #log.debug('chunker_sieve_function: calculated checksum = %s' % calculated_checksum)
                    sent_checksum = BinaryProtocolParameterDict.convert_word_to_int(raw_data[start+structure_len-2:start+structure_len])
                    if sent_checksum == calculated_checksum:
                        return_list.append((start, start+structure_len))        
                        #log.debug("chunker_sieve_function: found %s", raw_data[start:start+structure_len].encode('hex'))
        """
                
        return return_list
    
    def _filter_capabilities(self, events):
        """
        """ 
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    ########################################################################
    # overridden superclass methods
    ########################################################################

    def _get_response(self, timeout=10, expected_prompt=None):
        """
        Get a response from the instrument, and do not ignore white space as in base class method..        
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolExecption on timeout
        """
        # Grab time for timeout and wait for prompt.

        starttime = time.time()
        if expected_prompt == None:
            prompt_list = self._prompts.list()
        else:
            if isinstance(expected_prompt, str):
                prompt_list = [expected_prompt]
            else:
                prompt_list = expected_prompt

        while True:
            for item in prompt_list:
                if item in self._promptbuf:
                    return (item, self._linebuf)
                else:
                    time.sleep(.1)

            if time.time() > starttime + timeout:
                log.debug("_get_response: promptbuf=%s (%s)" %(self._promptbuf, self._promptbuf.encode("hex")))
                raise InstrumentTimeoutException("in InstrumentProtocol._get_response()")

    def _navigate_and_execute(self, cmd, **kwargs):
        """
        Navigate to a sub-menu and execute a list of commands instead of just one command as in the base class.  
        @param cmds The list of commands to execute.
        @param expected_prompt optional kwarg passed through to do_cmd_resp.
        @param timeout=timeout optional wakeup and command timeout.
        @param write_delay optional kwarg passed through to do_cmd_resp.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """

        # Get dest_submenu 
        dest_submenu = kwargs.pop('dest_submenu', None)
        if dest_submenu == None:
            raise InstrumentProtocolException('_navigate_and_execute(): dest_submenu parameter missing')

        # iterate through the directions 
        directions_list = self._menu.get_directions(dest_submenu)
        for directions in directions_list:
            log.debug('_navigate_and_execute: directions: %s' %(directions))
            command = directions.get_command()
            response = directions.get_response()
            timeout = directions.get_timeout()
            self._do_cmd_resp(command, expected_prompt = response, timeout = timeout)

        command = cmd
        while command != None:
            log.debug('_navigate_and_execute: sending cmd:%s, kwargs: %s to _do_cmd_resp.' 
                      %(command, kwargs))
            command = self._do_cmd_resp(command, **kwargs)

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        Perform a command-response on the device. 
        Send commands a character at a time to spoon feed instrument so it doesn't drop characters!
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional command timeout.
        @retval resp_result The (possibly parsed) response result.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """

        # Get timeout and final response.
        timeout = kwargs.get('timeout', 10)
        expected_prompt = kwargs.get('expected_prompt', None)

        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            raise InstrumentProtocolException('_do_cmd_resp: Cannot build command: %s' % cmd)
        
        (cmd_line, expected_response, next_cmd) = build_handler(command=cmd, **kwargs)
        if expected_prompt == None:
            expected_prompt = expected_response
            
        # Send command.
        log.debug('mavs4InstrumentProtocol._do_cmd_resp: <%s> (%s), timeout=%s, expected_prompt=%s, expected_prompt(hex)=%s,' 
                  %(cmd_line, cmd_line.encode("hex"), timeout, expected_prompt, 
                    expected_prompt.encode("hex") if expected_prompt != None else ''))
        for char in cmd_line:       
            self._linebuf = ''      # Clear line and prompt buffers for result.
            self._promptbuf = ''
            log.debug('mavs4InstrumentProtocol._do_cmd_resp: sending char <%s>' %char)
            self._connection.send(char)
            # Wait for the character to be echoed, timeout exception
            self._get_response(timeout, expected_prompt='%s'%char)
        self._connection.send(INSTRUMENT_NEWLINE)
        log.debug('mavs4InstrumentProtocol._do_cmd_resp: command sent, looking for response')
        (prompt, result) = self._get_response(timeout, expected_prompt=expected_prompt)
        resp_handler = self._response_handlers.get(cmd, None)
        if resp_handler:
            resp_result = resp_handler(result, prompt, **kwargs)
        else:
            resp_result = None
        if next_cmd == None:
            next_cmd = resp_result
        return next_cmd
   
    def _go_to_root_menu(self):
        # try to get main menu if instrument is not sleeping by sending one control-c
        self._linebuf = ''
        self._promptbuf = ''
        self._connection.send(InstrumentCmds.CONTROL_C)
        try:
            (prompt, result) = self._get_response(timeout= 2, expected_prompt=[InstrumentPrompts.MAIN_MENU])
        except:
            log.debug("_go_to_root_menu: instrument must be asleep, will try to wake it up")
        else:
            log.debug("_go_to_root_menu: got main menu prompt")
            if prompt == InstrumentPrompts.MAIN_MENU:
                return
        for attempt in range(0,5):
            self._linebuf = ''
            self._promptbuf = ''
            log.debug("_go_to_root_menu: sending 3 control-c characters to wake up sleeping instrument")
            # need to spoon feed this instrument or it drops characters (sigh!)
            self._connection.send(InstrumentCmds.CONTROL_C)
            time.sleep(.1)
            self._connection.send(InstrumentCmds.CONTROL_C)
            time.sleep(.1)
            self._connection.send(InstrumentCmds.CONTROL_C)
            (prompt, result) = self._get_response(timeout= 4,
                                                  expected_prompt=[InstrumentPrompts.MAIN_MENU,
                                                                   InstrumentPrompts.SLEEP_WAKEUP,
                                                                   InstrumentPrompts.SLEEPING])
            log.debug("_go_to_root_menu: got prompt %s" %prompt)
            if prompt == InstrumentPrompts.MAIN_MENU:
                return
                
                          
    def _float_to_string(self, v):
        """
        Write a float value to string formatted for "generic" set operations.
        Subclasses should overload this as needed for instrument-specific
        formatting.
        
        @param v A float val.
        @retval a float string formatted for "generic" set operations.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v,float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            return str(v)
                

    def _build_keypress_command(self, **kwargs):
        """
        Builder for simple, non-EOLN-terminated commands
        over-ridden to return dictionary expected by this classes _do_cmd_resp() method

        @param cmd The command to build
        @param args Unused arguments
        @ retval list with:
            The command to be sent to the device
            The response expected from the device (set to None to indicate not specified)
            The next command to be sent to device (set to None to indicate not specified)
        """
        cmd = kwargs.get('command', None)
        if cmd == None:
            raise InstrumentParameterException('_build_keypress_command: command not specified.')
        return ("%s" %(cmd), None, None)
    
    ########################################################################
    # State Unknown handlers.
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
        Discover current state; can be COMMAND or AUTOSAMPLE.  If the instrument is sleeping
        consider that to be in command state.
        @retval (next_state, result), (ProtocolStates.COMMAND or ProtocolStates.AUTOSAMPLE, None) if successful.
        """
        next_state = None
        result = None
        
        # try to wakeup the device using timeout if passed.
        timeout = kwargs.get('timeout', INSTRUMENT_TIMEOUT)
        try:
            prompt = self._get_prompt(timeout)
        except InstrumentTimeoutException:
            # didn't get any command mode prompt, so...
            # might be in deployed mode and sending data or 
            # might be in 'deployed' mode with monitor off or 
            # maybe not connected to an instrument at all
            next_state = ProtocolStates.AUTOSAMPLE
            result = ProtocolStates.AUTOSAMPLE
        else:
            # got one of the prompts, so device is in command mode           
            next_state = ProtocolStates.COMMAND
            result = ProtocolStates.COMMAND
            
        return (next_state, result)


    ########################################################################
    # State Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.
        self._update_params()
        
        log.debug("parameters values are: %s" %str(self._param_dict.get_config()))

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

        # Retrieve required parameter from args.
        # Raise exception if no parameter provided, or not a dict.
        try:
            params_to_set = args[0]           
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')
        else:
            if not isinstance(params_to_set, dict):
                raise InstrumentParameterException('Set parameters not a dict.')
        
        for (key, val) in params_to_set.iteritems():
            # go to root menu.
            got_prompt = False
            for i in range(10):
                try:
                    self._go_to_root_menu()
                    got_prompt = True
                    break
                except:
                    pass
                
            if not got_prompt:                
                raise InstrumentTimeoutException()
                                    
            dest_submenu = self._param_dict.get_menu_path_write(key)
            command = self._param_dict.get_submenu_write(key)
            self._navigate_and_execute(command, name=key, value=val, dest_submenu=dest_submenu, timeout=5)

        self._update_params()
            
        return (next_state, result)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (SBE37ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        result = None

        self._go_to_root_menu()
        # Issue start command and switch to autosample if successful.
        self._navigate_and_execute(InstrumentCmds.DEPLOY_GO, 
                                   dest_submenu=SubMenues.DEPLOY, 
                                   timeout=20, 
                                   expected_prompt=InstrumentPrompts.DEPLOY,
                                   *args, **kwargs)
                
        next_state = ProtocolStates.AUTOSAMPLE        
        
        return (next_state, result)

    def _handler_command_test(self, *args, **kwargs):
        """
        Switch to test state to perform instrument tests.
        @retval (next_state, result) tuple, (SBE37ProtocolState.TEST, None).
        """
        next_state = None
        result = None

        next_state = ProtocolStates.TEST
        
        return (next_state, result)

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        result = None

        next_state = ProtocolStates.DIRECT_ACCESS
        
        return (next_state, result)

    def _handler_command_clock_sync(self, *args, **kwargs):
        """
        sync clock close to a second edge 
        @retval (next_state, result) tuple, (None, None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None

        str_time = get_timestamp_delayed("%M %S %d %H %y %m")
        byte_time = ''
        for v in str_time.split():
            byte_time += chr(int('0x'+v, base=16))
        values = str_time.split()
        log.info("_handler_command_clock_sync: time set to %s:m %s:s %s:d %s:h %s:y %s:M (%s)" %(values[0], values[1], values[2], values[3], values[4], values[5], byte_time.encode('hex'))) 
        self._do_cmd_resp(InstrumentCmds.SET_REAL_TIME_CLOCK, byte_time, **kwargs)

        return (next_state, (next_agent_state, result))

    
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
        Exit autosample state.
        """
        pass

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (SBE37ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        # Issue stop command and switch to command if successful.
        got_root_prompt = False
        for i in range(10):
            try:
                self._go_to_root_menu()
                got_root_prompt = True
                break
            except:
                pass
            
        if not got_root_prompt:                
            raise InstrumentTimeoutException()
        
        next_state = ProtocolStates.COMMAND

        return (next_state, result)
        
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

        self._do_cmd_direct(data)
                        
        return (next_state, result)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None

        next_state = ProtocolStates.COMMAND
            
        return (next_state, result)


    ########################################################################
    # Common handlers.
    ########################################################################

    def _handler_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @throws InstrumentParameterException if missing or invalid parameter.
        """
        next_state = None
        result = None

        # Retrieve the required parameter, raise if not present.
        try:
            params = args[0]

        except IndexError:
            raise InstrumentParameterException('Get command requires a parameter list or tuple.')

        # If all params requested, retrieve config.
        if params == DriverParameter.ALL:
            result = self._param_dict.get_config()

        # If not all params, confirm a list or tuple of params to retrieve.
        # Raise if not a list or tuple.
        # Retireve each key in the list, raise if any are invalid.
        else:
            if not isinstance(params, (list, tuple)):
                raise InstrumentParameterException('Get argument not a list or tuple.')
            result = {}
            for key in params:
                try:
                    val = self._param_dict.get(key)
                    result[key] = val

                except KeyError:
                    raise InstrumentParameterException(('%s is not a valid parameter.' % key))

        return (next_state, result)

    ########################################################################
    # Private helpers.
    ########################################################################
        
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with MAVS4 parameters.
        For each parameter key add value formatting function for set commands.
        """
        # The parameter dictionary.
        self._param_dict = Mavs4ProtocolParameterDict()
        
        # Add parameter handlers to parameter dictionary for instrument configuration parameters.
        self._param_dict.add(InstrumentParameters.SYS_CLOCK,
                             r'.*\[(.*)\].*', 
                             lambda match : match.group(1),
                             lambda string : string,
                             value='',
                             menu_path_read=SubMenues.ROOT,
                             submenu_read=InstrumentCmds.SET_TIME,
                             menu_path_write=SubMenues.SET_TIME,
                             submenu_write=InstrumentCmds.ENTER_TIME)

        self._param_dict.add(InstrumentParameters.NOTE1,
                             r'.*Notes 1\| (.*?)\r\n.*', 
                             lambda match : match.group(1),
                             lambda string : string,
                             value='',
                             menu_path_read=SubMenues.ROOT,
                             submenu_read=InstrumentCmds.DEPLOY_MENU,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_NOTE)

        self._param_dict.add(InstrumentParameters.NOTE2,
                             r'.*2\| (.*?)\r\n.*', 
                             lambda match : match.group(1),
                             lambda string : string,
                             value='',
                             menu_path_read=SubMenues.ROOT,
                             submenu_read=InstrumentCmds.DEPLOY_MENU,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_NOTE)

        self._param_dict.add(InstrumentParameters.NOTE3,
                             r'.*3\| (.*?)\r\n.*', 
                             lambda match : match.group(1),
                             lambda string : string,
                             value='',
                             menu_path_read=SubMenues.ROOT,
                             submenu_read=InstrumentCmds.DEPLOY_MENU,
                             menu_path_write=SubMenues.DEPLOY,
                             submenu_write=InstrumentCmds.SET_NOTE)

        self._param_dict.add(InstrumentParameters.MONITOR,
                             '', 
                             lambda line : int(line),
                             self._int_to_string,
                             value=0)

        self._param_dict.add(InstrumentParameters.QUERY_MODE,
                             '', 
                             lambda line : int(line),
                             self._int_to_string,
                             value=0)

        self._param_dict.add(InstrumentParameters.MEASUREMENT_FREQUENCY,
                             '', 
                             lambda line : float(line),
                             self._float_to_string,
                             value=0.0)

        self._param_dict.add(InstrumentParameters.MEASUREMENTS_PER_SAMPLE,
                             '', 
                             lambda line : int(line),
                             self._int_to_string,
                             value=0)

        self._param_dict.add(InstrumentParameters.SAMPLE_PERIOD,
                             '', 
                             lambda line : int(line),
                             self._int_to_string,
                             value=0)

        self._param_dict.add(InstrumentParameters.SAMPLES_PER_BURST,
                             '', 
                             lambda line : int(line),
                             self._int_to_string,
                             value=0)

        self._param_dict.add(InstrumentParameters.BURST_INTERVAL,
                             '', 
                             lambda line : int(line),
                             self._int_to_string,
                             value=0)

    def _build_command_handlers(self):
        # these build handlers will be called by the base class during the
        # navigate_and_execute sequence.        
        self._add_build_handler(InstrumentCmds.ENTER_NOTE, self._build_enter_note_command)
        self._add_build_handler(InstrumentCmds.SET_NOTE, self._build_set_note_command)
        self._add_build_handler(InstrumentCmds.DEPLOY_MENU, self._build_deploy_menu_command)
        self._add_build_handler(InstrumentCmds.ENTER_TIME, self._build_enter_time_command)
        self._add_build_handler(InstrumentCmds.SET_TIME, self._build_set_time_command)
        self._add_build_handler(InstrumentCmds.ANSWER_YES, self._build_answer_yes_command)
        #self._add_build_handler(InstrumentCmds.DEPLOY_GO, self._build_deploy_go_command)
        
        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.SET_TIME, self._parse_time_response)
        self._add_response_handler(InstrumentCmds.DEPLOY_MENU, self._parse_deploy_menu_response)
        
    def _build_enter_note_command(self, **kwargs):
        """
        Build handler for note set command 
        @ retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device (set to None to indicate there isn't one)
        """
        value = kwargs.get('value', None)
        if value == None:
            raise InstrumentParameterException('set note command requires a value.')
        cmd = value
        log.debug("_build_enter_note_command: cmd=%s" %cmd)
        return (cmd, InstrumentPrompts.DEPLOY_MENU, None)

    def _build_set_note_command(self, **kwargs):
        """
        Build handler for note set command 
        @ retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device 
        """
        name = kwargs.get('name', None)
        if name == None:
            raise InstrumentParameterException('set note command requires a name.')
        cmd = "%s" %(name[-1])
        log.debug("_build_set_note_command: cmd=%s" %cmd)
        return (cmd, InstrumentPrompts.NOTE_INPUT, InstrumentCmds.ENTER_NOTE)

    def _build_deploy_menu_command(self, **kwargs):
        """
        Build handler for entering deploy menu command 
        @ retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device (set to None to indicate there isn't one)
        """
        cmd = InstrumentCmds.DEPLOY_MENU
        log.debug("_build_deploy_menu_command: cmd=%s" %cmd)
        return (cmd, InstrumentPrompts.DEPLOY_MENU, None)

    def _build_enter_time_command(self, **kwargs):
        """
        Build handler for time set command 
        String cmd constructed by param dict formatting function.
        @ retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device
        """
        val = kwargs.get('value', None)
        if val == None:
            raise InstrumentParameterException('set time command requires a value.')
        cmd = self._param_dict.format(InstrumentParameters.SYS_CLOCK, val)
        log.debug("_build_enter_time_command: cmd=%s" %cmd)
        return (cmd, InstrumentPrompts.SET_TIME, InstrumentCmds.ANSWER_YES)

    def _build_set_time_command(self, **kwargs):
        """
        Build handler for time set command 
        @ retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device (set to None to indicate there isn't one)
        """
        cmd = InstrumentCmds.SET_TIME
        log.debug("_build_set_time_command: cmd=%s" %cmd)
        return (cmd, InstrumentPrompts.SET_TIME, None)

    def _build_answer_yes_command(self, **kwargs):
        """
        Build handler for answer yes command 
        @ retval list with:
            The command to be sent to the device
            The response expected from the device
            The next command to be sent to device (set to None to indicate there isn't one)
        """
        cmd = InstrumentCmds.ANSWER_YES
        log.debug("_build_answer_yes_command: cmd=%s" %cmd)
        return (cmd, InstrumentPrompts.SET_TIME, None)

    def _parse_time_response(self, response, prompt, **kwargs):
        """
        Parse handler for time command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.GET_TIME in response:
            raise InstrumentProtocolException('get time command not recognized by instrument: %s.' % response)
        
        log.debug("_parse_time_response: response=%s" %response)

        if not self._param_dict.update(InstrumentParameters.SYS_CLOCK, response.splitlines()[-1]):
            log.debug('_parse_time_response: Failed to parse %s' %InstrumentParameters.SYS_CLOCK)
        return None
              
    def _parse_deploy_menu_response(self, response, prompt, **kwargs):
        """
        Parse handler for deploy command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        @ retval The next command to be sent to device (set to None to indicate there isn't one)
        """
        if not InstrumentPrompts.DEPLOY_MENU in response:
            raise InstrumentProtocolException('deploy menu command not recognized by instrument: %s.' %response)
        
        for parameter in DeployMenuParameters.list():
            #log.debug('_parse_deploy_menu_response: name=%s, response=%s' %(parameter, response))
            if not self._param_dict.update(parameter, response):
                log.debug('_parse_deploy_menu_response: Failed to parse %s' %parameter)
        return None
              
    def  _get_prompt(self, timeout, delay=2):
        """
        _wakeup is replaced by this method for this instrument to search for 
        prompt strings at other than just the end of the line.  There is no 
        'wakeup' for this instrument when it is in 'deployed' mode,
        so the best that can be done is to see if it responds or not.
        
        Clear buffers and send some CRs to the instrument
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        # Clear the prompt buffer.
        self._promptbuf = ''
        
        # Grab time for timeout.
        starttime = time.time()
        
        # get longest prompt to match by sorting the prompts longest to shortest
        prompts = self._sorted_longest_to_shortest(self._prompts.list())
        log.debug("prompts=%s" %prompts)
        
        while True:
            # Send a line return and wait a 2 sec.
            log.debug('Sending 2 newlines to get a response from the instrument.')
            # Send two newlines to attempt to wake the MAVS-4 device and get a response.
            # need to spoon feed this instrument or it drops characters (sigh!)
            self._connection.send(INSTRUMENT_NEWLINE)
            time.sleep(.1)
            self._connection.send(INSTRUMENT_NEWLINE)
            time.sleep(delay)
            
            for item in prompts:
                if item in self._promptbuf:
                    log.debug('_get_prompt got prompt: %s' % repr(item))
                    return item

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Issue the upload command. The response
        needs to be iterated through a line at a time and valuse saved.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        if self.get_current_state() != ProtocolStates.COMMAND:
            raise InstrumentStateException('Can not perform update of parameters when not in command state',
                                           error_code=InstErrorCode.INCORRECT_STATE)
        # Get old param dict config.
        old_config = self._param_dict.get_config()
        
        deploy_menu_prameters_parsed = False
        
        params_to_get = [InstrumentParameters.SYS_CLOCK,
                         InstrumentParameters.NOTE1,
                         InstrumentParameters.NOTE2,
                         InstrumentParameters.NOTE3]

        for key in params_to_get:
            if key in DeployMenuParameters.list():
                if deploy_menu_prameters_parsed == True:
                    continue
                else:
                    deploy_menu_prameters_parsed = True
            # go to root menu.
            got_prompt = False
            for i in range(10):
                try:
                    self._go_to_root_menu()
                    got_prompt = True
                    break
                except:
                    pass
                
            if not got_prompt:                
                raise InstrumentTimeoutException()
                                    
            dest_submenu = self._param_dict.get_menu_path_read(key)
            command = self._param_dict.get_submenu_read(key)
            self._navigate_and_execute(command, name=key, dest_submenu=dest_submenu, timeout=10)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
            
    def _sorted_longest_to_shortest(self, list):
        sorted_list = sorted(list, key=len, reverse=True)
        #log.debug("list=%s \nsorted=%s" %(list, sorted_list))
        return sorted_list
