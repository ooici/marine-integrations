#!/usr/bin/env python

"""
@package ion.services.mi.sbe16_driver
@file ion/services/mi/sbe16_driver.py
@author David Everett 
@brief Driver class for sbe16plus V2 CTD instrument.
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import logging
import time
import re
import datetime
from threading import Timer

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException

#import ion.services.mi.mi_logger
mi_logger = logging.getLogger('mi_logger')

###############################################################################
# Module-wide values
###############################################################################

###############################################################################
# Static enumerations for this class
###############################################################################

class SBE16Command(BaseEnum):
        DS  = 'ds'
        DCAL = 'dcal' # DHE dcal replaces dc
        TS = 'ts'
        STARTNOW = 'startnow'
        STOP = 'stop'
        TC = 'tc'
        TT = 'tt'
        TP = 'tp'
        SET = 'set'

class SBE16ProtocolState(BaseEnum):
    """
    Protocol states for SBE16. Cherry picked from DriverProtocolState
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    TEST = DriverProtocolState.TEST
    CALIBRATE = DriverProtocolState.CALIBRATE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    
class SBE16ProtocolEvent(BaseEnum):
    """
    Protocol events for SBE16. Cherry picked from DriverEvent enum.
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    TEST = DriverEvent.TEST
    RUN_TEST = DriverEvent.RUN_TEST
    CALIBRATE = DriverEvent.CALIBRATE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    FORCE_STATE = DriverEvent.FORCE_STATE


# Device specific parameters.
class SBE16Parameter(DriverParameter):
    """
    Device parameters for SBE16.
    """
    OUTPUTSAL = 'OUTPUTSAL'
    OUTPUTSV = 'OUTPUTSV'
    NAVG = 'NAVG'
    SAMPLENUM = 'SAMPLENUM'
    INTERVAL = 'INTERVAL'
    # DHE
    # SBE 16plus doesn't do this
    #STORETIME = 'STORETIME'
    TXREALTIME = 'TXREALTIME'
    SYNCMODE = 'SYNCMODE'
    # DHE This doesn't show up in status when SYNCMODE
    # is disabled, so the tests fail.  Commenting out for 
    # now.
    #SYNCWAIT = 'SYNCWAIT'
    TCALDATE = 'TCALDATE'
    TA0 = 'TA0'
    TA1 = 'TA1'
    TA2 = 'TA2'
    TA3 = 'TA3'
    CCALDATE = 'CCALDATE'
    CG = 'CG'
    CH = 'CH'
    CI = 'CI'
    CJ = 'CJ'
    # DHE
    # SBE 16plus doesn't do this
    #WBOTC = 'WBOTC'
    CTCOR = 'CTCOR'
    CPCOR = 'CPCOR'
    # Our SBE 16plus doesn't have a pressure sensor 
    #PCALDATE = 'PCALDATE'
    #PA0 = 'PA0'
    #PA1 = 'PA1'
    #PA2 = 'PA2'
    #PTCA0 = 'PTCA0'
    #PTCA1 = 'PTCA1'
    #PTCA2 = 'PTCA2'
    #PTCB0 = 'PTCB0'
    #PTCB1 = 'PTCB1'
    #PTCB2 = 'PTCB2'
    #POFFSET = 'POFFSET'
    # SBE 16plus doesn't do this
    #RCALDATE = 'RCALDATE'
    #RTCA0 = 'RTCA0'
    #RTCA1 = 'RTCA1'
    #RTCA2 = 'RTCA2'
    
    
# Device prompts.
class SBE16Prompt(BaseEnum):
    """
    SBE16 io prompts.
    """
    COMMAND = 'S>'
    BAD_COMMAND = '?cmd S>'
    #AUTOSAMPLE = 'S>\r\n'
    AUTOSAMPLE = 'S>'
    EXECUTED = '<Executed/>'

# SBE16 newline.
SBE16_NEWLINE = '\r\n'

# SBE16 default timeout.
SBE16_TIMEOUT = 10
                
# Packet config for SBE16 data granules.
PACKET_CONFIG = {
        'ctd_parsed' : ('prototype.sci_data.stream_defs', 'ctd_stream_packet'),
        'ctd_raw' : None            
}

###############################################################################
# Seabird Electronics 16plus V2 MicroCAT Driver.
###############################################################################

class InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass for SBE16 driver.
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    def __init__(self, evt_callback):
        """
        InstrumentDriver constructor.
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
        return SBE16Parameter.list()        

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = SBE16Protocol(SBE16Prompt, SBE16_NEWLINE, self._driver_event)

###############################################################################
# Seabird Electronics 37-SMP MicroCAT protocol.
###############################################################################

class SBE16Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class for SBE16 driver.
    Subclasses CommandResponseInstrumentProtocol
    """
    def __init__(self, prompts, newline, driver_event):
        """
        SBE16Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The SBE16 newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)
        
        # Build SBE16 protocol state machine.
        self._protocol_fsm = InstrumentFSM(SBE16ProtocolState, SBE16ProtocolEvent,
                            SBE16ProtocolEvent.ENTER, SBE16ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(SBE16ProtocolState.UNKNOWN, SBE16ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(SBE16ProtocolState.UNKNOWN, SBE16ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(SBE16ProtocolState.UNKNOWN, SBE16ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(SBE16ProtocolState.UNKNOWN, SBE16ProtocolEvent.FORCE_STATE, self._handler_unknown_force_state) 
        self._protocol_fsm.add_handler(SBE16ProtocolState.COMMAND, SBE16ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(SBE16ProtocolState.COMMAND, SBE16ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(SBE16ProtocolState.COMMAND, SBE16ProtocolEvent.ACQUIRE_SAMPLE, self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(SBE16ProtocolState.COMMAND, SBE16ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(SBE16ProtocolState.COMMAND, SBE16ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(SBE16ProtocolState.COMMAND, SBE16ProtocolEvent.SET, self._handler_command_set)
        self._protocol_fsm.add_handler(SBE16ProtocolState.COMMAND, SBE16ProtocolEvent.TEST, self._handler_command_test)
        self._protocol_fsm.add_handler(SBE16ProtocolState.AUTOSAMPLE, SBE16ProtocolEvent.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(SBE16ProtocolState.AUTOSAMPLE, SBE16ProtocolEvent.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(SBE16ProtocolState.AUTOSAMPLE, SBE16ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(SBE16ProtocolState.AUTOSAMPLE, SBE16ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(SBE16ProtocolState.TEST, SBE16ProtocolEvent.ENTER, self._handler_test_enter)
        self._protocol_fsm.add_handler(SBE16ProtocolState.TEST, SBE16ProtocolEvent.EXIT, self._handler_test_exit)
        self._protocol_fsm.add_handler(SBE16ProtocolState.TEST, SBE16ProtocolEvent.RUN_TEST, self._handler_test_run_tests)
        self._protocol_fsm.add_handler(SBE16ProtocolState.TEST, SBE16ProtocolEvent.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(SBE16ProtocolState.DIRECT_ACCESS, SBE16ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(SBE16ProtocolState.DIRECT_ACCESS, SBE16ProtocolEvent.EXIT, self._handler_direct_access_exit)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(SBE16Command.DS, self._build_simple_command)
        # DHE dcal replaces dc
        self._add_build_handler(SBE16Command.DCAL, self._build_simple_command)
        self._add_build_handler(SBE16Command.TS, self._build_simple_command)
        self._add_build_handler(SBE16Command.STARTNOW, self._build_simple_command)
        self._add_build_handler(SBE16Command.STOP, self._build_simple_command)
        self._add_build_handler(SBE16Command.TC, self._build_simple_command)
        self._add_build_handler(SBE16Command.TT, self._build_simple_command)
        self._add_build_handler(SBE16Command.TP, self._build_simple_command)
        self._add_build_handler(SBE16Command.SET, self._build_set_command)

        # Add response handlers for device commands.
        self._add_response_handler(SBE16Command.DS, self._parse_dsdc_response)
        # DHE dcal replaces dc
        self._add_response_handler(SBE16Command.DCAL, self._parse_dcal_response)
        self._add_response_handler(SBE16Command.TS, self._parse_ts_response)
        self._add_response_handler(SBE16Command.SET, self._parse_set_response)
        self._add_response_handler(SBE16Command.TC, self._parse_test_response)
        self._add_response_handler(SBE16Command.TT, self._parse_test_response)
        self._add_response_handler(SBE16Command.TP, self._parse_test_response)

        # Add sample handlers.
        # DHE: replaced the pattern because our borrowed SBE16 doesn't have a pressure sensor 
        #self._sample_pattern = r'^#? *(-?\d+\.\d+), *(-?\d+\.\d+), *(-?\d+\.\d+)'
        self._sample_pattern = r'^#? *(-?\d+\.\d+), *(-?\d+\.\d+) *'
        self._sample_pattern += r'(, *(-?\d+\.\d+))?(, *(-?\d+\.\d+))?'
        self._sample_pattern += r'(, *(\d+) +([a-zA-Z]+) +(\d+), *(\d+):(\d+):(\d+))?'
        self._sample_pattern += r'(, *(\d+)-(\d+)-(\d+), *(\d+):(\d+):(\d+))?'        
        self._sample_regex = re.compile(self._sample_pattern)

        # State state machine in UNKNOWN state. 
        self._protocol_fsm.start(SBE16ProtocolState.UNKNOWN)

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
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result), (SBE16ProtocolState.COMMAND or
        SBE16State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the device response does not correspond to
        an expected state.
        """
        next_state = None
        result = None
        
        # Wakeup the device with timeout if passed.
        timeout = kwargs.get('timeout', SBE16_TIMEOUT)
        prompt = self._wakeup(timeout)
        prompt = self._wakeup(timeout)
        
        # Set the state to change.
        # Raise if the prompt returned does not match command or autosample.
        if prompt == SBE16Prompt.COMMAND or prompt == SBE16Prompt.EXECUTED:
            next_state = SBE16ProtocolState.COMMAND
            result = SBE16ProtocolState.COMMAND
        elif prompt == SBE16Prompt.AUTOSAMPLE:
            next_state = SBE16ProtocolState.AUTOSAMPLE
            result = SBE16ProtocolState.AUTOSAMPLE
        else:
            raise InstrumentProtocolException('Failure to recognize device state.')
            
        return (next_state, result)

    def _handler_unknown_force_state(self, *args, **kwargs):
        """
        Force driver into a given state for the purposes of unit testing 
        @param state=desired_state Required desired state to transition to.
        @raises InstrumentParameterException if no state parameter.
        """

        state = kwargs.get('state', None)  # via kwargs
        if state is None:
            raise InstrumentParameterException('Missing state parameter.')

        next_state = state
        result = state
        
        return (next_state, result)


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
                result = self._do_cmd_resp(SBE16Command.SET, key, val, **kwargs)
            self._update_params()
            
        return (next_state, result)

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from SBE16.
        @retval (next_state, result) tuple, (None, sample dict).        
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """
        next_state = None
        result = None

        result = self._do_cmd_resp(SBE16Command.TS, *args, **kwargs)
        
        return (next_state, result)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (SBE16ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        next_state = None
        result = None

        # Assure the device is transmitting.
        if not self._param_dict.get(SBE16Parameter.TXREALTIME):
            self._do_cmd_resp(SBE16Command.SET, SBE16Parameter.TXREALTIME, True, **kwargs)
        
        # Issue start command and switch to autosample if successful.
        self._do_cmd_no_resp(SBE16Command.STARTNOW, *args, **kwargs)
                
        next_state = SBE16ProtocolState.AUTOSAMPLE        
        
        return (next_state, result)

    def _handler_command_test(self, *args, **kwargs):
        """
        Switch to test state to perform instrument tests.
        @retval (next_state, result) tuple, (SBE16ProtocolState.TEST, None).
        """
        next_state = None
        result = None

        next_state = SBE16ProtocolState.TEST
        
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
        @retval (next_state, result) tuple, (SBE16ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', SBE16_TIMEOUT)
        self._wakeup_until(timeout, SBE16Prompt.AUTOSAMPLE)

        # Issue the stop command.
        self._do_cmd_resp(SBE16Command.STOP, *args, **kwargs)        
        
        # Prompt device until command prompt is seen.
        self._wakeup_until(timeout, SBE16Prompt.COMMAND)
        
        next_state = SBE16ProtocolState.COMMAND

        return (next_state, result)
        
    ########################################################################
    # Common handlers.
    ########################################################################

    def _handler_command_autosample_test_get(self, *args, **kwargs):
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
    # Test handlers.
    ########################################################################

    def _handler_test_enter(self, *args, **kwargs):
        """
        Enter test state. Setup the secondary call to run the tests.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.        
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        
        # Forward the test event again to run the test handler and
        # switch back to command mode afterward.
        Timer(1, lambda: self._protocol_fsm.on_event(SBE16ProtocolEvent.RUN_TEST)).start()
    
    def _handler_test_exit(self, *args, **kwargs):
        """
        Exit test state.
        """
        pass

    def _handler_test_run_tests(self, *args, **kwargs):
        """
        Run test routines and validate results.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        tc_pass = False
        tt_pass = False
        #tp_pass = False
        tc_result = None
        tt_result = None
        #tp_result = None

        test_result = {}

        try:
            tc_pass, tc_result = self._do_cmd_resp(SBE16Command.TC, timeout=200)
            tt_pass, tt_result = self._do_cmd_resp(SBE16Command.TT, timeout=200)
            # DHE: our SBE16 has no pressure sensor
            #tp_pass, tp_result = self._do_cmd_resp(SBE16Command.TP, timeout=200)
        
        except Exception as e:
            test_result['exception'] = e
            test_result['message'] = 'Error running instrument tests.'
        
        finally:
            test_result['cond_test'] = 'Passed' if tc_pass else 'Failed'
            test_result['cond_data'] = tc_result
            test_result['temp_test'] = 'Passed' if tt_pass else 'Failed'
            test_result['temp_data'] = tt_result
            # DHE: our SBE16 has no pressure sensor
            #test_result['pres_test'] = 'Passed' if tp_pass else 'Failed'
            #test_result['pres_data'] = tp_result
            #test_result['success'] = 'Passed' if (tc_pass and tt_pass and tp_pass) else 'Failed'
            test_result['success'] = 'Passed' if (tc_pass and tt_pass) else 'Failed'
            
        self._driver_event(DriverAsyncEvent.TEST_RESULT, test_result)
        next_state = SBE16ProtocolState.COMMAND
 
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
    
    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        pass

    ########################################################################
    # Private helpers.
    ########################################################################
        
    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the SBE16 device.
        """
        self._connection.send(SBE16_NEWLINE)
                
    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Wake the device then issue
        display status and display calibration commands. The parameter
        dict will match line output and udpate itself.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """

        
        # Get old param dict config.
        old_config = self._param_dict.get_config()
        
        # Issue display commands and parse results.
        timeout = kwargs.get('timeout', SBE16_TIMEOUT)
        self._do_cmd_resp(SBE16Command.DS,timeout=timeout)
        self._do_cmd_resp(SBE16Command.DCAL,timeout=timeout)
        
        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
        
    def _build_simple_command(self, cmd):
        """
        Build handler for basic SBE16 commands.
        @param cmd the simple sbe16 command to format.
        @retval The command to be sent to the device.
        """
        return cmd+SBE16_NEWLINE
    
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
            
            # DHE TEMPTEMP
            #print 'param is: ' + param
            if param == 'INTERVAL':
                param = 'sampleinterval'

            set_cmd = '%s=%s' % (param, str_val)
            set_cmd = set_cmd + SBE16_NEWLINE
            
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)
            
        return set_cmd

    def _parse_set_response(self, response, prompt):
        """
        Parse handler for set command.
        @param response command response string.
        @param prompt prompt following command response.        
        @throws InstrumentProtocolException if set command misunderstood.
        """
        if prompt != SBE16Prompt.COMMAND:
            raise InstrumentProtocolException('Set command not recognized: %s' % response)

    def _parse_dsdc_response(self, response, prompt):
        """
        Parse handler for dsdc commands.
        @param response command response string.
        @param prompt prompt following command response.        
        @throws InstrumentProtocolException if dsdc command misunderstood.
        """
        if prompt not in [SBE16Prompt.COMMAND, SBE16Prompt.EXECUTED]: 
            raise InstrumentProtocolException('dsdc command not recognized: %s.' % response)

        for line in response.split(SBE16_NEWLINE):
            print line
            if 'sample interval' in line:
                for sline in line.split(','):
                    #print 'DHE: split this: ' + sline.lstrip()
                    self._param_dict.update(sline.lstrip())
            elif 'output salinity' in line:
                for sline in line.split(','):
                    #print 'DHE: split this: ' + sline.lstrip()
                    self._param_dict.update(sline.lstrip())
            else: 
                self._param_dict.update(line)
            
    def _parse_dcal_response(self, response, prompt):
        """
        Parse handler for dsdc commands.
        @param response command response string.
        @param prompt prompt following command response.        
        @throws InstrumentProtocolException if dsdc command misunderstood.
        """
        if prompt not in [SBE16Prompt.COMMAND, SBE16Prompt.EXECUTED]:
            raise InstrumentProtocolException('dcal command not recognized: %s.' % response)
            
        for line in response.split(SBE16_NEWLINE):
            # DHE TEMPTEMP
            #print line
            self._param_dict.update(line)
        
    def _parse_ts_response(self, response, prompt):
        """
        Response handler for ts command.
        @param response command response string.
        @param prompt prompt following command response.
        @retval sample dictionary containig c, t, d values.
        @throws InstrumentProtocolException if ts command misunderstood.
        @throws InstrumentSampleException if response did not contain a sample
        """
        
        if prompt not in [SBE16Prompt.COMMAND, SBE16Prompt.EXECUTED]:
            raise InstrumentProtocolException('ts command not recognized: %s', response)
        
        sample = None
        for line in response.split(SBE16_NEWLINE):
            sample = self._extract_sample(line, True)
            if sample:
                break
        
        if not sample:     
            raise SampleException('Response did not contain sample: %s' % repr(response))
            
        return sample
                
    def _parse_test_response(self, response, prompt):
        """
        Do minimal checking of test outputs.
        @param response command response string.
        @param promnpt prompt following command response.
        @retval tuple of pass/fail boolean followed by response
        """
        
        success = False
        lines = response.split()
        if len(lines)>2:
            data = lines[1:-1]
            bad_count = 0
            for item in data:
                try:
                    float(item)
                    
                except ValueError:
                    bad_count += 1
            
            if bad_count == 0:
                success = True
        
        return (success, response)        
                
    def got_data(self, paPacket):
        """
        Callback for receiving new data from the device.
        """
        paLength = paPacket.get_data_size()
        data = paPacket.get_data()

        # Call the superclass to update line and prompt buffers.
        CommandResponseInstrumentProtocol.got_data(self, data)

        # If in streaming mode, process the buffer for samples to publish.
        cur_state = self.get_current_state()
        if cur_state == SBE16ProtocolState.AUTOSAMPLE:
            if SBE16_NEWLINE in self._linebuf:
                lines = self._linebuf.split(SBE16_NEWLINE)
                self._linebuf = lines[-1]
                for line in lines:
                    self._extract_sample(line)                    
                
    def _extract_sample(self, line, publish=True):
        """
        Extract sample from a response line if present and publish to agent.
        @param line string to match for sample.
        @param publsih boolean to publish sample (default True).
        @retval Sample dictionary if present or None.
        """
        sample = None
        match = self._sample_regex.match(line)
        if match:
            sample = {}
            sample['t'] = [float(match.group(1))]
            sample['c'] = [float(match.group(2))]
            #sample['p'] = [float(match.group(3))]

            # Driver timestamp.
            sample['time'] = [time.time()]
            sample['stream_name'] = 'ctd_parsed'

            if self._driver_event:
                self._driver_event(DriverAsyncEvent.SAMPLE, sample)

        return sample            
        
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with SBE16 parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.        
        self._param_dict.add(SBE16Parameter.OUTPUTSAL,
                             #r'(do not )?output salinity with each sample',
                             r'output salinity = (no)',
                             lambda match : False if match.group(1) else True,
                             self._true_false_to_string)
        self._param_dict.add(SBE16Parameter.OUTPUTSV,
                             #r'(do not )?output sound velocity with each sample',
                             r'output sound velocity = (no)',
                             lambda match : False if match.group(1) else True,
                             self._true_false_to_string)
        self._param_dict.add(SBE16Parameter.NAVG,
                             #r'number of samples to average = (\d+)',
                             r'number of measurements per sample = (\d+)',
                             lambda match : int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(SBE16Parameter.SAMPLENUM,
                             #r'samplenumber = (\d+), free = \d+',
                             r'samples = (\d+), free = \d+',
                             lambda match : int(match.group(1)),
                             self._int_to_string)
        self._param_dict.add(SBE16Parameter.INTERVAL,
                             r'sample interval = (\d+) seconds',
                             lambda match : int(match.group(1)),
                             self._int_to_string)
        # DHE: 16plus does not do this
        #self._param_dict.add(SBE16Parameter.STORETIME,
        #                     r'(do not )?store time with each sample',
        #                     lambda match : False if match.group(1) else True,
        #                     self._true_false_to_string)
        self._param_dict.add(SBE16Parameter.TXREALTIME,
                             #r'(do not )?transmit real-time data',
                             r'transmit real-time = (yes|no)',
                             #lambda match : False if match.group(1) else True,
                             lambda match : True if match.group(1)=='yes' else False,
                             self._true_false_to_string)
        self._param_dict.add(SBE16Parameter.SYNCMODE,
                             r'serial sync mode (enabled|disabled)',
                             lambda match : False if (match.group(1)=='disabled') else True,
                             self._true_false_to_string)
        # DHE This doesn't show up in status when SYNCMODE
        # is disabled, so the tests fail.  Commenting out for 
        # now.
        #self._param_dict.add(SBE16Parameter.SYNCWAIT,
        #                     r'wait time after serial sync sampling = (\d+) seconds',
        #                     lambda match : int(match.group(1)),
        #                     self._int_to_string)
        self._param_dict.add(SBE16Parameter.TCALDATE,
                             r'temperature: +((\d+)-([a-zA-Z]+)-(\d+))',
                             lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
                             self._date_to_string)
        self._param_dict.add(SBE16Parameter.TA0,
                             #r' +TA0 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             r' +TA0 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE16Parameter.TA1,
                             r' +TA1 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE16Parameter.TA2,
                             r' +TA2 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE16Parameter.TA3,
                             r' +TA3 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE16Parameter.CCALDATE,
                             r'conductivity: +((\d+)-([a-zA-Z]+)-(\d+))',
                             lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
                             self._date_to_string)
        self._param_dict.add(SBE16Parameter.CG,
                             r' +G = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE16Parameter.CH,
                             r' +H = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE16Parameter.CI,
                             r' +I = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        self._param_dict.add(SBE16Parameter.CJ,
                             r' +J = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        #
        # DHE SBE16 doesn't have this parameter
        #
        #self._param_dict.add(SBE16Parameter.WBOTC,
        #                     r' +WBOTC = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #
        # DHE SBE16 different than SBE16
        #
        self._param_dict.add(SBE16Parameter.CTCOR,
                             r' +CTCOR = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
                             lambda match : float(match.group(1)),
                             self._float_to_string)
        #
        # DHE SBE16 different than SBE16
        #
        #self._param_dict.add(SBE16Parameter.CPCOR,
        #                     r' +CPCOR = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #self._param_dict.add(SBE16Parameter.PCALDATE,
        #                     r'pressure .+ ((\d+)-([a-zA-Z]+)-(\d+))',
        #                     lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
        #                     self._date_to_string)
        #self._param_dict.add(SBE16Parameter.PA0,
        #                     r' +PA0 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #self._param_dict.add(SBE16Parameter.PA1,
        #                     r' +PA1 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #self._param_dict.add(SBE16Parameter.PA2,
        #                     r' +PA2 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #self._param_dict.add(SBE16Parameter.PTCA0,
        #                     r' +PTCA0 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #self._param_dict.add(SBE16Parameter.PTCA1,
        #                     r' +PTCA1 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #self._param_dict.add(SBE16Parameter.PTCA2,
        #                     r' +PTCA2 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #self._param_dict.add(SBE16Parameter.PTCB0,
        #                     r' +PTCSB0 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                    self._float_to_string)
        #self._param_dict.add(SBE16Parameter.PTCB1,
        #                     r' +PTCSB1 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #self._param_dict.add(SBE16Parameter.PTCB2,
        #                     r' +PTCSB2 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #self._param_dict.add(SBE16Parameter.POFFSET,
        #                     r' +POFFSET = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #self._param_dict.add(SBE16Parameter.RCALDATE,
        #                     r'rtc: +((\d+)-([a-zA-Z]+)-(\d+))',
        #                     lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
        #                     self._date_to_string)
        #self._param_dict.add(SBE16Parameter.RTCA0,
        #                     r' +RTCA0 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #self._param_dict.add(SBE16Parameter.RTCA1,
        #                     r' +RTCA1 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
        #self._param_dict.add(SBE16Parameter.RTCA2,
        #                     r' +RTCA2 = (-?\d.\d\d\d\d\d\de[-+]\d\d)',
        #                     lambda match : float(match.group(1)),
        #                     self._float_to_string)
    

    ########################################################################
    # Static helpers to format set commands.
    ########################################################################

    @staticmethod
    def _true_false_to_string(v):
        """
        Write a boolean value to string formatted for sbe16 set operations.
        @param v a boolean value.
        @retval A yes/no string formatted for sbe16 set operations.
        @throws InstrumentParameterException if value not a bool.
        """
        
        if not isinstance(v,bool):
            raise InstrumentParameterException('Value %s is not a bool.' % str(v))
        if v:
            return 'y'
        else:
            return 'n'

    @staticmethod
    def _int_to_string(v):
        """
        Write an int value to string formatted for sbe16 set operations.
        @param v An int val.
        @retval an int string formatted for sbe16 set operations.
        @throws InstrumentParameterException if value not an int.
        """
        
        if not isinstance(v,int):
            raise InstrumentParameterException('Value %s is not an int.' % str(v))
        else:
            return '%i' % v

    @staticmethod
    def _float_to_string(v):
        """
        Write a float value to string formatted for sbe16 set operations.
        @param v A float val.
        @retval a float string formatted for sbe16 set operations.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v,float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            return '%e' % v

    @staticmethod
    def _date_to_string(v):
        """
        Write a date tuple to string formatted for sbe16 set operations.
        @param v a date tuple: (day,month,year).
        @retval A date string formatted for sbe16 set operations.
        @throws InstrumentParameterException if date tuple is not valid.
        """

        if not isinstance(v,(list,tuple)):
            raise InstrumentParameterException('Value %s is not a list, tuple.' % str(v))
        
        if not len(v)==3:
            raise InstrumentParameterException('Value %s is not length 3.' % str(v))
        
        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep',
                  'Oct','Nov','Dec']
        day = v[0]
        month = v[1]
        year = v[2]
        
        if len(str(year)) > 2:
            year = int(str(year)[-2:])
        
        if not isinstance(day,int) or day < 1 or day > 31:
            raise InstrumentParameterException('Value %s is not a day of month.' % str(day))
        
        if not isinstance(month,int) or month < 1 or month > 12:
            raise InstrumentParameterException('Value %s is not a month.' % str(month))

        if not isinstance(year,int) or year < 0 or year > 99:
            raise InstrumentParameterException('Value %s is not a 0-99 year.' % str(year))
        
        return '%02i-%s-%02i' % (day,months[month-1],year)

    @staticmethod
    def _string_to_date(datestr,fmt):
        """
        Extract a date tuple from an sbe16 date string.
        @param str a string containing date information in sbe16 format.
        @retval a date tuple.
        @throws InstrumentParameterException if datestr cannot be formatted to
        a date.
        """
        if not isinstance(datestr,str):
            raise InstrumentParameterException('Value %s is not a string.' % str(datestr))
        try:
            date_time = time.strptime(datestr,fmt)
            date = (date_time[2],date_time[1],date_time[0])

        except ValueError:
            raise InstrumentParameterException('Value %s could not be formatted to a date.' % str(datestr))
                        
        return date

