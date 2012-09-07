#!/usr/bin/env python

"""
@package mi.instrument.nobska.mavs4.mavs4.driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4/mavs4/driver.py
@author Bill Bollenbacher
@brief Driver for the mavs4
Release notes:

initial release
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'


#import logging
import time
import re
import datetime
import copy

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.instrument.instrument_protocol import MenuInstrumentProtocol
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
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

from mi.core.log import get_logger
log = get_logger()

###
#   Module wide values
###
#log = logging.getLogger('mi_logger')

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
    CHANGE_TIME = 'Change time & data (Yes/No)'
    
class InstrumentCmds(BaseEnum):
    EXIT_SUB_MENU = '\x03'   # CTRL-C (end of text)
    DEPLOY_GO     = '\a'     # CTRL-G (bell)
    SET_TIME      = '1'
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
    
class ProtocolEvents(BaseEnum):
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
    TEST = DriverEvent.TEST
    RUN_TEST = DriverEvent.RUN_TEST
    CALIBRATE = DriverEvent.CALIBRATE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT

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

class Channel(BaseEnum):
    """
    Enumerated driver channels.  
    """
    #CTD = DriverChannel.CTD
    #ALL = DriverChannel.ALL

#class Command(DriverCommand):
#    pass

class MetadataParameter(BaseEnum):
    pass

class Error(BaseEnum):
    pass

class Capability(BaseEnum):
    pass

class Status(BaseEnum):
    pass

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

# Packet config for MAVS-4 data granules.
# TODO: set this up for MAVS-4
PACKET_CONFIG = {
        'adcp_parsed' : ('prototype.sci_data.stream_defs', 'ctd_stream_packet'),
        'adcp_raw' : None            
}

class Mavs4ProtocolParameterDict(ProtocolParameterDict):
    
    def set_from_string(self, name, line):
        """
        Set a parameter value in the dictionary.
        @param name The parameter name.
        @param line The parameter value as a string.
        @raises KeyError if the name is invalid.
        """
        log.debug("Mavs4ProtocolParameterDict.set_from_string(): name=%s, line=%s" %(name, line))
        self._param_dict[name].value = self._param_dict[name].f_getval(line)

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
        
    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return InstrumentParameters.list()        

    def driver_echo(self, msg):
        """
        @brief Sample driver command. 
        """
        echo = 'driver_echo: %s' % msg
        return echo


###
#   Protocol for mavs4
###
class mavs4InstrumentProtocol(MenuInstrumentProtocol):
    """
    The protocol is a very simple command/response protocol with a few show
    commands and a few set commands.
    """
    
    upload_download_parameter_list = [
        'u',
        '',
        '#',
        InstrumentParameters.SYS_CLOCK,
        InstrumentParameters.BAUD_RATE,
        InstrumentParameters.VERSION_NUMBER,
        InstrumentParameters.CONFIG_INITIALIZED,
        InstrumentParameters.V_OFFSET_0,
        InstrumentParameters.V_OFFSET_1,
        InstrumentParameters.V_OFFSET_2,
        InstrumentParameters.V_OFFSET_3,
        InstrumentParameters.V_SCALE,
        InstrumentParameters.ANALOG_OUT,
        InstrumentParameters.COMPASS,
        InstrumentParameters.M0_OFFSET,
        InstrumentParameters.M1_OFFSET,
        InstrumentParameters.M2_OFFSET,
        InstrumentParameters.M0_SCALE,
        InstrumentParameters.M1_SCALE,
        InstrumentParameters.M2_SCALE,
        InstrumentParameters.TILT,
        InstrumentParameters.TY_OFFSET,
        InstrumentParameters.TX_OFFSET,
        InstrumentParameters.TY_SCALE,
        InstrumentParameters.TX_SCALE,
        InstrumentParameters.TY_TEMPCO,
        InstrumentParameters.TX_TEMPCO,
        InstrumentParameters.FAST_SENSOR,
        InstrumentParameters.THERMISTOR,
        InstrumentParameters.TH_OFFSET,
        InstrumentParameters.PRESSURE,
        InstrumentParameters.P_OFFSET,
        InstrumentParameters.P_SCALE,
        InstrumentParameters.P_MA,
        InstrumentParameters.AUXILIARY1,
        InstrumentParameters.A1_OFFSET,
        InstrumentParameters.A1_SCALE,
        InstrumentParameters.A1_MA,
        InstrumentParameters.AUXILIARY2,
        InstrumentParameters.A2_OFFSET,
        InstrumentParameters.A2_SCALE,
        InstrumentParameters.A2_MA,
        InstrumentParameters.AUXILIARY3,
        InstrumentParameters.A3_OFFSET,
        InstrumentParameters.A3_SCALE,
        InstrumentParameters.A3_MA,
        InstrumentParameters.SENSOR_ORIENTATION,
        InstrumentParameters.SERIAL_NUMBER,
        InstrumentParameters.QUERY_CHARACTER,
        InstrumentParameters.POWER_UP_TIME_OUT,
        '#',
        InstrumentParameters.DEPLOY_INITIALIZED,
        InstrumentParameters.LINE1,
        InstrumentParameters.LINE2,
        InstrumentParameters.LINE3,
        InstrumentParameters.START_TIME,
        InstrumentParameters.STOP_TIME,
        InstrumentParameters.FRAME,
        InstrumentParameters.DATA_MONITOR,
        InstrumentParameters.INTERNAL_LOGGING,
        InstrumentParameters.APPEND_MODE,
        InstrumentParameters.BYTES_PER_SAMPLE,
        InstrumentParameters.VERBOSE_MODE,
        InstrumentParameters.QUERY_MODE,
        InstrumentParameters.EXTERNAL_POWER,
        InstrumentParameters.MEASUREMENT_FREQUENCY,
        InstrumentParameters.MEASUREMENT_PERIOD_SECS,
        InstrumentParameters.MEASUREMENT_PERIOD_TICKS,
        InstrumentParameters.MEASUREMENTS_PER_SAMPLE,
        InstrumentParameters.SAMPLE_PERIOD_SECS,
        InstrumentParameters.SAMPLE_PERIOD_TICKS,
        InstrumentParameters.SAMPLES_PER_BURST,
        InstrumentParameters.INTERVAL_BETWEEN_BURSTS,
        InstrumentParameters.BURSTS_PER_FILE,
        InstrumentParameters.STORE_TIME,
        InstrumentParameters.STORE_FRACTIONAL_TIME,
        InstrumentParameters.STORE_RAW_PATHS,
        InstrumentParameters.PATH_UNITS,
        'DONE']
    
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
            SubMenues.SET_TIME   : [Directions("1", InstrumentPrompts.SUB_MENU)],
            SubMenues.FLASH_CARD : [Directions("2", InstrumentPrompts.SUB_MENU)],
            SubMenues.DEPLOY     : [Directions(InstrumentCmds.DEPLOY_MENU, InstrumentPrompts.SUB_MENU, 20)],
            SubMenues.PICO_DOS   : [Directions(SubMenues.FLASH_CARD),
                                    Directions("2", InstrumentPrompts.SUB_MENU)]
            })
        
        MenuInstrumentProtocol.__init__(self, menu, prompts, newline, driver_event)
                
        # these build handlers will be called by the base class during the
        # navigate_and_execute sequence.        
        self._add_build_handler(InstrumentCmds.DEPLOY_MENU, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DEPLOY_GO, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.EXIT_SUB_MENU, self._build_simple_command)
        self._add_build_handler(InstrumentCmds.UPLOAD, self._build_simple_command)
        
        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.UPLOAD, self._parse_upload_response)

        self._protocol_fsm = InstrumentFSM(ProtocolStates, 
                                           ProtocolEvents, 
                                           ProtocolEvents.ENTER,
                                           ProtocolEvents.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolStates.UNKNOWN, ProtocolEvents.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolStates.UNKNOWN, ProtocolEvents.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolStates.UNKNOWN, ProtocolEvents.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvents.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvents.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvents.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvents.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvents.GET, self._handler_get)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvents.TEST, self._handler_command_test)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvents.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvents.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvents.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvents.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvents.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvents.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvents.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvents.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Set state machine in UNKNOWN state. 
        self._protocol_fsm.start(ProtocolStates.UNKNOWN)


    ########################################################################
    # overridden superclass methods
    ########################################################################

    def _do_cmd_resp(self, cmd, *args, **kwargs):
        """
        Perform a command-response on the device.
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

        # Clear line and prompt buffers for result.
        self._linebuf = ''
        self._promptbuf = ''

        # Send command.
        log.debug('mavs4InstrumentProtocol._do_cmd_resp: %s, timeout=%s, expected_prompt=%s, expected_prompt(hex)=%s,' 
                  %(repr(cmd), timeout, expected_prompt, expected_prompt.encode("hex")))
        if cmd == InstrumentCmds.EXIT_SUB_MENU:
            self._connection.send(cmd)
        else:
            for char in cmd:
                self._connection.send(char)
                # Wait for the character to be echoed, timeout exception
                self._get_response(timeout, expected_prompt='%s'%char)
            self._connection.send(INSTRUMENT_NEWLINE)
        (prompt, result) = self._get_response(timeout, expected_prompt=expected_prompt)
        resp_handler = self._response_handlers.get(cmd, None)
        resp_result = None
        if resp_handler:
            resp_result = resp_handler(result, prompt)
        return resp_result
   
    def got_data(self, data):
        """
        Callback for receiving new data from the device.
        """
        if self.get_current_state() == ProtocolStates.DIRECT_ACCESS:
            # direct access mode
            if len(data) > 0:
                log.debug("mavs4InstrumentProtocol._got_data(): <" + data + ">") 
                if self._driver_event:
                    self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, data)
                    # TODO: what about logging this as an event?
            return
        
        if len(data)>0:
            # Call the superclass to update line and prompt buffers.
            MenuInstrumentProtocol.got_data(self, data)
    
            # If in streaming mode, process the buffer for samples to publish.
            cur_state = self.get_current_state()
            if cur_state == ProtocolStates.AUTOSAMPLE:
                if INSTRUMENT_NEWLINE in self._linebuf:
                    lines = self._linebuf.split(INSTRUMENT_NEWLINE)
                    self._linebuf = lines[-1]
                    for line in lines:
                        self._extract_sample(line)  
                        
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
        
        parameters = copy.copy(self._param_dict)    # get copy of parameters to modify
        
        # For each key, value in the params_to_set list set the value in parameters copy.
        try:
            for (name, value) in params_to_set.iteritems():
                log.debug('setting %s to %s' %(name, value))
                parameters.set_from_value(name, value)
        except Exception as ex:
            raise InstrumentProtocolException('Unable to set parameter %s to %s: %s' %(name, value, ex))
            
        output = self._create_set_output(parameters)
        
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
                                
        # Issue download command
        for i in range(2):
            try: 
                self._do_cmd_resp(InstrumentCmds.DOWNLOAD,
                                  expected_prompt=InstrumentPrompts.DOWNLOAD,
                                  timeout=2)
                got_prompt = True
                break
            except:
                pass

        if not got_prompt:                
            raise InstrumentTimeoutException()

        # for debugging
        #file = open("upload.txt", "w")

        done = False
        
        for line in output:
            for char in line:
                if char == InstrumentCmds.END_OF_TRANS:
                    # don't send newline after last '#'
                    done = True
                    break
                # Clear line and prompt buffers for result.
                self._linebuf = ''
                self._promptbuf = ''
                log.debug('_handler_command_set: sending %s from %s' %(char, line))
                self._connection.send(char)
                #file.write(char)
                # Wait for the character to be echoed, timeout exception
                # use method that looks for the response only at the end of the _promptbuf
                self._get_response(timeout=2, expected_prompt='%s'%char)
            if done == True:
                break
            self._linebuf = ''
            self._promptbuf = ''
            self._connection.send('\n')
            #file.write('\n')
            CommandResponseInstrumentProtocol._get_response(self, timeout=2, expected_prompt='\n')
             
        #file.close()

        result = self._do_cmd_resp(InstrumentCmds.END_OF_TRANS, 
                                   expected_prompt=InstrumentPrompts.SET_DONE,
                                   timeout=5)
        
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
        
        # Add parameter handlers to parameter dict for instrument configuration parameters.
        self._param_dict.add(InstrumentParameters.SYS_CLOCK,
                             '', 
                             lambda line : int(line),
                             self._int_to_string)
        
                             lambda line : line[:-1])

        self._param_dict.add(InstrumentParameters.DATA_MONITOR,
                             '', 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.QUERY_MODE,
                             '', 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.MEASUREMENT_FREQUENCY,
                             '', 
                             lambda line : float(line),
                             self._float_to_string)

        self._param_dict.add(InstrumentParameters.MEASUREMENTS_PER_SAMPLE,
                             '', 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.SAMPLE_PERIOD_SECS,
                             '', 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.SAMPLE_PERIOD_TICKS,
                             '', 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.SAMPLES_PER_BURST,
                             '', 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.INTERVAL_BETWEEN_BURSTS,
                             '', 
                             lambda line : int(line),
                             self._int_to_string)

    def  _get_prompt(self, timeout, delay=1):
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
                if item in self._promptbuf:
                    log.debug('wakeup got prompt: %s' % repr(item))
                    return item

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()

    def _extract_sample(self, line, publish=True):
        """
        Extract sample from a response line if present and publish to agent.
        @param line string to match for sample.
        @param publsih boolean to publish sample (default True).
        @retval Sample dictionary if present or None.
        """
        return  # TODO remove this when sample format is known
        
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
                                
        # Issue upload command
        for i in range(2):
            try: 
                self._do_cmd_resp(InstrumentCmds.UPLOAD,
                                  expected_prompt=InstrumentPrompts.UPLOAD,
                                  timeout=2)
                got_prompt = True
                break
            except:
                pass

        if not got_prompt:                
            raise InstrumentTimeoutException()

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _parse_upload_response(self, response, prompt):
        """
        Parse handler for upload command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if upload command misunderstood.
        """
        if prompt != InstrumentPrompts.UPLOAD:
            raise InstrumentProtocolException('upload command not recognized: %s.' % response)
        
        log.debug("_parse_upload_response: response=%s" %response)

        for name, line in zip(self.upload_download_parameter_list, response.split(INSTRUMENT_NEWLINE)):
            #log.debug("_parse_upload_response: name=%s, line=%s" %(name, line))
            if name == 'DONE':
                break
            if not line in ['u', '#', '']:
                self._param_dict.set_from_string(name, line)
              
    def _create_set_output(self, parameters):
        output = []
        for name in self.upload_download_parameter_list:
            if name == 'DONE':
                break
            if not name in ['u', '']:
                if name == '#':
                    output.append(name)
                else:
                    if name in [InstrumentParameters.DEPLOY_INITIALIZED, 
                                InstrumentParameters.LINE1,
                                InstrumentParameters.LINE2,
                                InstrumentParameters.LINE3]:
                        output.append(parameters.format_parameter(name) + '\r')
                    else:
                        output.append(parameters.format_parameter(name))
                              
        checksum = 0
        for item in output:
            for char in item:
                log.debug('c=%s, i=%s' %(char, item))
                checksum = (checksum + ord(char)) % 255
                
        output.append('#')
        checksum_str = "{:02X}".format(checksum)
        output.append(checksum_str)
        output.append('#' + InstrumentCmds.END_OF_TRANS)  # EOT to signal end of output
        
        return output



