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


import logging
import time
import re
import datetime

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException

from mi.core.log import log

###
#   Module wide values
###
#log = logging.getLogger('mi_logger')

INSTRUMENT_NEWLINE = '\r\n'

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
    OUTPUTSAL = 'OUTPUTSAL'

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

# Packet config for MAVS-4 data granules.
# TODO: set this up for MAVS-4
PACKET_CONFIG = {
        'adcp_parsed' : ('prototype.sci_data.stream_defs', 'ctd_stream_packet'),
        'adcp_raw' : None            
}

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
class mavs4InstrumentProtocol(CommandResponseInstrumentProtocol):
    """
    The protocol is a very simple command/response protocol with a few show
    commands and a few set commands.
    """
    
    def __init__(self, prompts, newline, driver_event):
        """
        """
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)
        
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
        """
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvents.ENTER, self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvents.EXIT, self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvents.GET, self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolStates.AUTOSAMPLE, ProtocolEvents.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample)
        self._protocol_fsm.add_handler(ProtocolStates.TEST, ProtocolEvents.ENTER, self._handler_test_enter)
        self._protocol_fsm.add_handler(ProtocolStates.TEST, ProtocolEvents.EXIT, self._handler_test_exit)
        self._protocol_fsm.add_handler(ProtocolStates.TEST, ProtocolEvents.RUN_TEST, self._handler_test_run_tests)
        self._protocol_fsm.add_handler(ProtocolStates.TEST, ProtocolEvents.GET, self._handler_command_autosample_test_get)
        """
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvents.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvents.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvents.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolStates.DIRECT_ACCESS, ProtocolEvents.STOP_DIRECT, self._handler_direct_access_stop_direct)

        # Set state machine in UNKNOWN state. 
        self._protocol_fsm.start(ProtocolStates.UNKNOWN)


    ########################################################################
    # overridden superclass methods
    ########################################################################

    def _send_wakeup(self):
        """
        Send two newlines to attempt to wake the MAVS-4 device and get a response.
        """
        self._connection.send(INSTRUMENT_NEWLINE + INSTRUMENT_NEWLINE)

    def  _wakeup(self, timeout, delay=1):
        """
        _wakeup is overridden for this instrument to search for prompt strings at other than
        just the end of the line.
        
        Clear buffers and send a wakeup command to the instrument
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
            log.debug('Sending wakeup.')
            self._send_wakeup()
            time.sleep(delay)
            
            for item in self._prompts.list():
                if item in self._promptbuf:
                    log.debug('wakeup got prompt: %s' % repr(item))
                    return item

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()

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
            CommandResponseInstrumentProtocol.got_data(self, data)
    
            # If in streaming mode, process the buffer for samples to publish.
            cur_state = self.get_current_state()
            if cur_state == ProtocolStates.AUTOSAMPLE:
                if INSTRUMENT_NEWLINE in self._linebuf:
                    lines = self._linebuf.split(INSTRUMENT_NEWLINE)
                    self._linebuf = lines[-1]
                    for line in lines:
                        self._extract_sample(line)                    
                

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
            prompt = self._wakeup(timeout)
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
        #self._update_params()

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

        # Issue start command and switch to autosample if successful.
        self._do_cmd_no_resp('startnow', *args, **kwargs)
                
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
            sample['p'] = [float(match.group(3))]

            # Driver timestamp.
            sample['time'] = [time.time()]
            sample['stream_name'] = 'ctd_parsed'

            if self._driver_event:
                self._driver_event(DriverAsyncEvent.SAMPLE, sample)

        return sample            
        
                




