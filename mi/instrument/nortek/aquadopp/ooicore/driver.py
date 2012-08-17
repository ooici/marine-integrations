"""
@package mi.instrument.nortek.aquadopp.ooicore.driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore/driver.py
@author Bill Bollenbacher
@brief Driver for the ooicore
Release notes:

Driver for Aquadopp DW
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

import time
import string

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.exceptions import InstrumentTimeoutException, \
                               InstrumentParameterException, \
                               InstrumentProtocolException, \
                               InstrumentStateException
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.common import InstErrorCode

from mi.core.log import get_logger ; log = get_logger()


# newline.
NEWLINE = '\n\r'

# default timeout.
TIMEOUT = 10

# Packet config
PACKET_CONFIG = {
    'parsed' : None,
    'raw' : None
}

# Device prompts.
class InstrumentPrompts(BaseEnum):
    """
    aquadopp prompts.
    """
    COMMAND_MODE  = 'Command mode'
    CONFIRMATION  = 'Confirm:'
    Z_ACK         = '\x06\x06'  # attach a 'Z' to the front of these two items to force them to the end of the list
    Z_NACK        = '\x15\x15'  # so the other responses will have priority to be detected if they are present

    
class InstrumentCmds(BaseEnum):
    CMD_WHAT_MODE         = 'II'   
    SAMPLE_WHAT_MODE      = 'I'   
    POWER_DOWN            = 'PD'     
    IDENTIFY              = 'ID'
    CONFIRMATION          = 'MC'
    SAMPLE_AVG_TIME       = 'A'
    SAMPLE_INTERVAL_TIME  = 'M'
    
class InstrumentModes(BaseEnum):
    FIRMWARE_UPGRADE = '\x00\x00\x06\x06'
    MEASUREMENT      = '\x01\x00\x06\x06'
    COMMAND          = '\x02\x00\x06\x06'
    DATA_RETRIEVAL   = '\x04\x00\x06\x06'
    CONFIRMATION     = '\x05\x00\x06\x06'
    

class ProtocolState(BaseEnum):
    """
    Protocol states
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    DISCOVER = DriverEvent.DISCOVER
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT

# Device specific parameters.
class Parameter(DriverParameter):
    """
    Device parameters
    """


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
        self._protocol = Protocol(InstrumentPrompts, NEWLINE, self._driver_event)

###############################################################################
# Protocol
################################################################################

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
        self._protocol_fsm = InstrumentFSM(ProtocolState, 
                                           ProtocolEvent,
                                           ProtocolEvent.ENTER, 
                                           ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER, self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT, self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.

        # Add response handlers for device commands.

        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)


    ########################################################################
    # overridden superclass methods
    ########################################################################

    def got_data(self, data):
        """
        Callback for receiving new data from the device.
        """
        if self.get_current_state() == ProtocolState.DIRECT_ACCESS:
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
            if cur_state == ProtocolState.AUTOSAMPLE:
                if NEWLINE in self._linebuf:
                    lines = self._linebuf.split(NEWLINE)
                    self._linebuf = lines[-1]
                    for line in lines:
                        self._extract_sample(line)  

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
        Discover current state of instrument; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result)
        """
        next_state = None
        result = None

        # try to discover the device mode using timeout if passed.
        timeout = kwargs.get('timeout', TIMEOUT)
        prompt = self._get_mode(timeout)
        if prompt == InstrumentPrompts.COMMAND_MODE:
            next_state = ProtocolState.COMMAND
            result = ProtocolState.COMMAND
        elif prompt == InstrumentPrompts.CONFIRMATION:    
            next_state = ProtocolState.AUTOSAMPLE
            result = ProtocolState.AUTOSAMPLE
        elif prompt == InstrumentPrompts.Z_ACK:
            log.debug('_handler_unknown_discover: promptbuf = \n%s\n%s' %(self._promptbuf, self._promptbuf.encode("hex")))
            if InstrumentModes.COMMAND in self._promptbuf:
                next_state = ProtocolState.COMMAND
                result = ProtocolState.COMMAND
            elif (InstrumentModes.MEASUREMENT in self._promptbuf or 
                 InstrumentModes.CONFIRMATION in self._promptbuf):
                next_state = ProtocolState.AUTOSAMPLE
                result = ProtocolState.AUTOSAMPLE
            else:
                raise InstrumentStateException('Unknown state.')
        else:
            raise InstrumentStateException('Unknown state.')

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

    def _handler_command_start_direct(self):
        """
        """
        next_state = None
        result = None

        next_state = ProtocolState.DIRECT_ACCESS

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

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return (next_state, result)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None

        next_state = ProtocolState.COMMAND

        return (next_state, result)

    ########################################################################
    # Private helpers.
    ########################################################################
        
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Issue the upload command. The response
        needs to be iterated through a line at a time and valuse saved.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """
        if self.get_current_state() != ProtocolState.COMMAND:
            raise InstrumentStateException('Can not perform update of parameters when not in command state',
                                           error_code=InstErrorCode.INCORRECT_STATE)
        # Get old param dict config.
        old_config = self._param_dict.get_config()
        # TODO: get params from the instrument

    def _extract_sample(self, line, publish=True):
        """
        Extract sample from a response line if present and publish to agent.
        @param line string to match for sample.
        @param publsih boolean to publish sample (default True).
        @retval Sample dictionary if present or None.
        """
        return  # TODO remove this when sample format is known
        
    def  _get_mode(self, timeout, delay=1):
        """
        _wakeup is replaced by this method for this instrument to search for 
        prompt strings at other than just the end of the line.  
        @param timeout The timeout to wake the device.
        @param delay The time to wait between consecutive wakeups.
        @throw InstrumentTimeoutException if the device could not be woken.
        """
        # Clear the prompt buffer.
        self._promptbuf = ''
        
        # Grab time for timeout.
        starttime = time.time()
        
        while True:
            log.debug('Sending what_mode command to get a response from the instrument.')
            # Send what_mode command to attempt to get a response.
            self._connection.send(InstrumentCmds.CMD_WHAT_MODE)
            time.sleep(delay)
            
            for item in self._prompts.list():
                if item in self._promptbuf:
                    if item != InstrumentPrompts.Z_NACK:
                        log.debug('get_mode got prompt: %s' % repr(item))
                        return item

            if time.time() > starttime + timeout:
                raise InstrumentTimeoutException()

