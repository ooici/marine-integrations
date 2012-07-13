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

from mi.core.common import BaseEnum
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
    MAIN_MENU = '\a\b ? \a\b'
    SUB_MENU  = '\a\b'
    PICO_DOS  = 'Enter command >> '
    SLEEPING  = 'Sleeping . . .'
    WAKEUP    = 'Enter <CTRL>-<C> now to wake up?'
    DEPLOY    = '>>> <CTRL>-<C> to terminate deployment <<<'
    UPLOAD    = '\x04'    # EOT
    DOWNLOAD  = ' \a'
    
class InstrumentCmds(BaseEnum):
    EXIT_SUB_MENU = '\x03'   # CTRL-C
    DEPLOY_GO     = '\a'     # CTRL-G (bell)
    DEPLOY_MENU   = '6'
    UPLOAD        = 'u'
    DOWNLOAD      = 'b'

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
    BAUD_RATE = 'BaudRate'
    VERSION_NUMBER = 'VersionNumber'
    CONFIG_INITIALIZED = 'ConfigInitialized'
    V_OFFSET_0 = 'V_offset_0'
    V_OFFSET_1 = 'V_offset_1'
    V_OFFSET_2 = 'V_offset_2'
    V_OFFSET_3 = 'V_offset_3'
    V_SCALE = 'V_scale'
    ANALOG_OUT = 'AnalogOut'
    COMPASS = 'Compass'
    M0_OFFSET = 'M0_offset'
    M1_OFFSET = 'M1_offset'
    M2_OFFSET = 'M2_offset'
    M0_SCALE = 'M0_scale'
    M1_SCALE = 'M1_scale'
    M2_SCALE = 'M2_scale'
    TILT = 'Tilt'
    TY_OFFSET = 'TY_offset'
    TX_OFFSET = 'TX_offset'
    TY_SCALE = 'TY_scale'
    TX_SCALE = 'TX_scale'
    TY_TEMPCO = 'TY_tempco'
    TX_TEMPCO = 'TX_tempco'
    FAST_SENSOR = 'FastSensor'
    THERMISTOR = 'Thermistor'
    TH_OFFSET = 'Th_offset'
    PRESSURE = 'Pressure'
    P_OFFSET = 'P_offset'
    P_SCALE = 'P_scale'
    P_MA = 'P_mA'
    AUXILIARY1 = 'Auxiliary1'
    A1_OFFSET = 'A1_offset'
    A1_SCALE = 'A1_scale'
    A1_MA = 'A1_mA'
    AUXILIARY2 = 'Auxiliary2'
    A2_OFFSET = 'A2_offset'
    A2_SCALE = 'A2_scale'
    A2_MA = 'A2_mA'
    AUXILIARY3 = 'Auxiliary3'
    A3_OFFSET = 'A3_offset'
    A3_SCALE = 'A3_scale'
    A3_MA = 'A3_mA'
    SENSOR_ORIENTATION = 'SensorOrientation'
    SERIAL_NUMBER = 'SerialNumber'
    QUERY_CHARACTER = 'QueryCharacter'
    POWER_UP_TIME_OUT = 'PowerUpTimeOut'
    DEPLOY_INITIALIZED = 'DeployInitialized'
    LINE1 = 'line1'
    LINE2 = 'line2'
    LINE3 = 'line3'
    START_TIME = 'StartTime'
    STOP_TIME = 'StopTime'
    FRAME = 'FRAME'
    DATA_MONITOR = 'DataMonitor'
    INTERNAL_LOGGING = 'InternalLogging'
    APPEND_MODE = 'AppendMode'
    BYTES_PER_SAMPLE = 'BytesPerSample'
    VERBOSE_MODE = 'VerboseMode'
    QUERY_MODE = 'QueryMode'
    EXTERNAL_POWER = 'ExternalPower'
    MEASUREMENT_FREQUENCY = 'MeasurementFrequency'
    MEASUREMENT_PERIOD_SECS = 'MeasurementPeriod.secs'
    MEASUREMENT_PERIOD_TICKS = 'MeasurementPeriod.ticks'
    MEASUREMENTS_PER_SAMPLE = 'MeasurementsPerSample'
    SAMPLE_PERIOD_SECS = 'SamplePeriod.secs'
    SAMPLE_PERIOD_TICKS = 'SamplePeriod.ticks'
    SAMPLES_PER_BURST = 'SamplesPerBurst'
    INTERVAL_BETWEEN_BURSTS = 'IntervalBetweenBursts'
    BURSTS_PER_FILE = 'BurstsPerFile'
    STORE_TIME = 'StoreTime'
    STORE_FRACTIONAL_TIME = 'StoreFractionalTime'
    STORE_RAW_PATHS = 'StoreRawPaths'
    PATH_UNITS = 'PathUnits'

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
    
    def set(self, name, line):
        """
        Set a parameter value in the dictionary.
        @param name The parameter name.
        @param value The parameter value.
        @raises KeyError if the name is invalid.
        """
        self._param_dict[name] = self.f_getval(line)
        

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
    
    upload_parameter_list = [
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
        InstrumentParameters.PATH_UNITS]
    
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
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvents.TEST, self._handler_command_test)
        self._protocol_fsm.add_handler(ProtocolStates.COMMAND, ProtocolEvents.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvents.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvents.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvents.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        """
        self._protocol_fsm.add_handler(ProtocolStates.TEST, ProtocolEvents.ENTER, self._handler_test_enter)
        self._protocol_fsm.add_handler(ProtocolStates.TEST, ProtocolEvents.EXIT, self._handler_test_exit)
        self._protocol_fsm.add_handler(ProtocolStates.TEST, ProtocolEvents.RUN_TEST, self._handler_test_run_tests)
        self._protocol_fsm.add_handler(ProtocolStates.TEST, ProtocolEvents.GET, self._handler_command_autosample_test_get)
        """
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
        self._do_cmd_resp(InstrumentCmds.EXIT_SUB_MENU, expected_prompt=InstrumentPrompts.MAIN_MENU, timeout=2)
                          
                

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

        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
        try:
            params = args[0]
            
        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')

        if not isinstance(params, dict):
            raise InstrumentParameterException('Set parameters not a dict.')
        
        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        else:
            
            for (key, val) in params.iteritems():
                result = self._do_cmd_resp('set', key, val, **kwargs)
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
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.BAUD_RATE,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.VERSION_NUMBER,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.CONFIG_INITIALIZED,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.V_OFFSET_0,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.V_OFFSET_1,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.V_OFFSET_2,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.V_OFFSET_3,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.V_SCALE,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.ANALOG_OUT,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.COMPASS,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.M0_OFFSET,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.M1_OFFSET,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.M2_OFFSET,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.M0_SCALE,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.M1_SCALE,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.M2_SCALE,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.TILT,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.TY_OFFSET,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.TX_OFFSET,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.TY_SCALE,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.TX_SCALE,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.TY_TEMPCO,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.TX_TEMPCO,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.FAST_SENSOR,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.THERMISTOR,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.TH_OFFSET,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.PRESSURE,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.P_OFFSET,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.P_SCALE,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.P_MA,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.AUXILIARY1,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.A1_OFFSET,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.A1_SCALE,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.A1_MA,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.AUXILIARY2,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.A2_OFFSET,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.A2_SCALE,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.A2_MA,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.AUXILIARY3,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.A3_OFFSET,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.A3_SCALE,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.A3_MA,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)
        
        self._param_dict.add(InstrumentParameters.SENSOR_ORIENTATION,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.SERIAL_NUMBER,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        self._param_dict.add(InstrumentParameters.QUERY_CHARACTER,
                             None, 
                             lambda line : line,
                             lambda line : line)
        
        self._param_dict.add(InstrumentParameters.POWER_UP_TIME_OUT,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)
        
        # Add parameter handlers to parameter dict for instrument deployment parameters.
        self._param_dict.add(InstrumentParameters.DEPLOY_INITIALIZED,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.LINE1,
                             None, 
                             lambda line : line,
                             lambda line : line)

        self._param_dict.add(InstrumentParameters.LINE2,
                             None, 
                             lambda line : line,
                             lambda line : line)

        self._param_dict.add(InstrumentParameters.LINE3,
                             None, 
                             lambda line : line,
                             lambda line : line)

        self._param_dict.add(InstrumentParameters.START_TIME,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.STOP_TIME,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.FRAME,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.DATA_MONITOR,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.INTERNAL_LOGGING,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.APPEND_MODE,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.BYTES_PER_SAMPLE,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.VERBOSE_MODE,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.QUERY_MODE,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.EXTERNAL_POWER,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.MEASUREMENT_FREQUENCY,
                             None, 
                             lambda line : float(line),
                             self._float_to_string)

        self._param_dict.add(InstrumentParameters.MEASUREMENT_PERIOD_SECS,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.MEASUREMENT_PERIOD_TICKS,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.MEASUREMENTS_PER_SAMPLE,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.SAMPLE_PERIOD_SECS,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.SAMPLE_PERIOD_TICKS,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.SAMPLES_PER_BURST,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.INTERVAL_BETWEEN_BURSTS,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.BURSTS_PER_FILE,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.STORE_TIME,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.STORE_FRACTIONAL_TIME,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.STORE_RAW_PATHS,
                             None, 
                             lambda line : int(line),
                             self._int_to_string)

        self._param_dict.add(InstrumentParameters.PATH_UNITS,
                             None, 
                             lambda line : line,
                             lambda line : line)

    def  _get_prompt(self, timeout, delay=1):
        """
        _wakeup is replaced by this method for this instrument to search for prompt strings at other than
        just the end of the line.  There is no 'wakeup' for this instrument when it is in 'deployed' mode,
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
        needs to be interated through a line at a time and valuse saved.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        if self.get_current_state() != ProtocolStates.COMMAND:
            raise InstrumentStateException('Can not perform update of parameters when not in command state',
                                           error_code=InstErrorCode.INCORRECT_STATE)
        # Get old param dict config.
        old_config = self._param_dict.get_config()

        # go to root menu.
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
                                
        # Issue upload command 
        self._do_cmd_resp(InstrumentCmds.UPLOAD,
                          expected_prompt=InstrumentPrompts.UPLOAD)

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

        for name, line in zip(self.upload_parameter_list, response.split(INSTRUMENT_NEWLINE)):
            self._param_dict.set(name, line)
              




