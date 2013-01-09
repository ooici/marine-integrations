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
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.common import InstErrorCode
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue, CommonDataParticleType

from mi.core.log import get_logger
log = get_logger()


class DataParticleType(BaseEnum):
    RAW = CommonDataParticleType.RAW

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
    MAIN_MENU   = '\a\b ? \a\b'
    SUB_MENU    = '\a\b'
    PICO_DOS    = 'Enter command >> '
    SLEEPING    = 'Sleeping . . .'
    WAKEUP      = 'Enter <CTRL>-<C> now to wake up?'
    DEPLOY      = '>>> <CTRL>-<C> to terminate deployment <<<'
    UPLOAD      = '\x04'    # EOT
    DOWNLOAD    = ' \a'
    SET_DONE    = 'New parameters accepted.'
    SET_FAILED  = 'Invalid entry'
    SET_TIME    = '] ? \a\b'
    GET_TIME    = 'Enter correct time ['
    CHANGE_TIME = 'Change time & date (Yes/No) [N] ?\a\b'
    
class InstrumentCmds(BaseEnum):
    EXIT_SUB_MENU = '\x03'   # CTRL-C (end of text)
    DEPLOY_GO     = '\a'     # CTRL-G (bell)
    SET_TIME      = '1'
    ENTER_TIME    = ''
    ANSWER_YES    = 'y'
    DEPLOY_MENU   = '6'
    UPLOAD        = 'u'
    DOWNLOAD      = 'b'
    END_OF_TRANS  = '\x04'   # CTRL-D (end of transmission)

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
    DATA_MONITOR = 'DataMonitor'
    QUERY_MODE = 'QueryMode'
    MEASUREMENT_FREQUENCY = 'MeasurementFrequency'
    MEASUREMENTS_PER_SAMPLE = 'MeasurementsPerSample'
    SAMPLE_PERIOD_SECS = 'SamplePeriod.secs'
    SAMPLE_PERIOD_TICKS = 'SamplePeriod.ticks'
    SAMPLES_PER_BURST = 'SamplesPerBurst'
    INTERVAL_BETWEEN_BURSTS = 'IntervalBetweenBursts'

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

class Mavs4ProtocolParameterDict(ProtocolParameterDict):
    
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
        log.debug('Mavs4ProtocolParameterDict.update(): set %s from %s' %(name, response))
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
            SubMenues.DEPLOY     : [Directions(InstrumentCmds.DEPLOY_MENU, InstrumentPrompts.SUB_MENU, 20)]
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

        # these build handlers will be called by the base class during the
        # navigate_and_execute sequence.        
        self._add_build_handler(InstrumentCmds.ENTER_TIME, self._build_time_command)
        self._add_build_handler(InstrumentCmds.SET_TIME, self._build_keypress_command)
        self._add_build_handler(InstrumentCmds.ANSWER_YES, self._build_keypress_command)
        self._add_build_handler(InstrumentCmds.DEPLOY_MENU, self._build_keypress_command)
        self._add_build_handler(InstrumentCmds.DEPLOY_GO, self._build_keypress_command)
        self._add_build_handler(InstrumentCmds.EXIT_SUB_MENU, self._build_keypress_command)
        
        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.SET_TIME, self._parse_time_response)

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
                if self._promptbuf.endswith(item):
                    return (item, self._linebuf)
                else:
                    time.sleep(.1)

            if time.time() > starttime + timeout:
                log.debug("_get_response: promptbuf=%s (%s)" %(self._promptbuf, self._promptbuf.encode("hex")))
                raise InstrumentTimeoutException("in InstrumentProtocol._get_response()")

    def _navigate_and_execute(self, cmds, **kwargs):
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

        resp_result = None

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

        for interaction in cmds:
            command = interaction[0]
            response = interaction[1]
            log.debug('_navigate_and_execute: sending cmd: %s with expected response %s and kwargs: %s to _do_cmd_resp.' 
                      %(command, response, kwargs))
            resp_result = self._do_cmd_resp(command, expected_prompt = response, **kwargs)
 
        return resp_result

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
        
        value = kwargs.get('value', None)

        cmd_line = build_handler(cmd, value)
        
        self._linebuf = ''
        self._promptbuf = ''
        
        # Send command.
        log.debug('mavs4InstrumentProtocol._do_cmd_resp: <%s> (%s), timeout=%s, expected_prompt=%s, expected_prompt(hex)=%s,' 
                  %(cmd_line, cmd_line.encode("hex"), timeout, expected_prompt, expected_prompt.encode("hex")))
        if cmd_line == InstrumentCmds.EXIT_SUB_MENU:
            self._connection.send(cmd_line)
        else:
            for char in cmd_line:        # Clear line and prompt buffers for result.
                self._linebuf = ''
                self._promptbuf = ''
                log.debug('mavs4InstrumentProtocol._do_cmd_resp: sending char <%s>' %char)
                self._connection.send(char)
                # Wait for the character to be echoed, timeout exception
                self._get_response(timeout, expected_prompt='%s'%char)
            self._connection.send(INSTRUMENT_NEWLINE)
        log.debug('mavs4InstrumentProtocol._do_cmd_resp: command sent, looking for response')
        (prompt, result) = self._get_response(timeout, expected_prompt=expected_prompt)
        resp_handler = self._response_handlers.get(cmd, None)
        resp_result = None
        if resp_handler:
            resp_result = resp_handler(result, prompt)
        return resp_result
   
    def _go_to_root_menu(self):
        self._do_cmd_resp(InstrumentCmds.EXIT_SUB_MENU, expected_prompt=InstrumentPrompts.MAIN_MENU, timeout=4)
                          
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
            commands = self._param_dict.get_submenu_write(key)
            self._navigate_and_execute(commands, value=val, dest_submenu=dest_submenu, timeout=5)

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
                             submenu_read=[[InstrumentCmds.SET_TIME, InstrumentPrompts.SET_TIME]],
                             menu_path_write=SubMenues.SET_TIME,
                             submenu_write=[[InstrumentCmds.ENTER_TIME, InstrumentPrompts.SET_TIME],
                                            [InstrumentCmds.ANSWER_YES, InstrumentPrompts.SET_TIME]])

        self._param_dict.add(InstrumentParameters.DATA_MONITOR,
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

        self._param_dict.add(InstrumentParameters.SAMPLE_PERIOD_SECS,
                             '', 
                             lambda line : int(line),
                             self._int_to_string,
                             value=0)

        self._param_dict.add(InstrumentParameters.SAMPLE_PERIOD_TICKS,
                             '', 
                             lambda line : int(line),
                             self._int_to_string,
                             value=0)

        self._param_dict.add(InstrumentParameters.SAMPLES_PER_BURST,
                             '', 
                             lambda line : int(line),
                             self._int_to_string,
                             value=0)

        self._param_dict.add(InstrumentParameters.INTERVAL_BETWEEN_BURSTS,
                             '', 
                             lambda line : int(line),
                             self._int_to_string,
                             value=0)

    def  _get_prompt(self, timeout, delay=4):
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
        
        while True:
            # Send a line return and wait a sec.
            log.debug('Sending 2 newlines to get a response from the instrument.')
            # Send two newlines to attempt to wake the MAVS-4 device and get a response.
            self._connection.send(INSTRUMENT_NEWLINE + INSTRUMENT_NEWLINE)
            time.sleep(delay)
            
            for item in self._prompts.list():
                if self._promptbuf.endswith(item):
                    log.debug('wakeup got prompt: %s' % repr(item))
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
        
        params_to_get = [InstrumentParameters.SYS_CLOCK]

        for key in params_to_get:
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
            commands = self._param_dict.get_submenu_read(key)
            self._navigate_and_execute(commands, dest_submenu=dest_submenu, timeout=5)


        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _build_time_command(self, throw_away, val):
        """
        Build handler for time set command 
        String cmd constructed by param dict formatting function.
        @ retval The set command to be sent to the device.
        """
        cmd = self._param_dict.format(InstrumentParameters.SYS_CLOCK, val)
 
        log.debug("_build_time_command: cmd=%s" %cmd)
        return cmd

    def _parse_time_response(self, response, prompt):
        """
        Parse handler for upload command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        """
        if not InstrumentPrompts.GET_TIME in response:
            raise InstrumentProtocolException('get time command not recognized: %s.' % response)
        
        log.debug("_parse_time_response: response=%s" %response)

        if not self._param_dict.update(InstrumentParameters.SYS_CLOCK, response.splitlines()[-1]):
            log.debug('_parse_time_response: Failed to parse %s' %InstrumentParameters.SYS_CLOCK)
              

