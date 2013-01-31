"""
@package mi.instrument.seabird.driver
@file mi/instrument/seabird/driver.py
@author Roger Unwin
@brief Base class for seabird instruments
Release notes:

None.
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver

from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverEvent

from mi.core.exceptions import InstrumentProtocolException
from mi.core.time import get_timestamp_delayed

NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 10

###############################################################################
# Driver
###############################################################################

class SeaBirdInstrumentDriver(SingleConnectionInstrumentDriver):
    """
    Base class for all seabird instrument drivers.
    """
    def __init__(self, evt_callback):
        """
        Driver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)
#        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED,
#            DriverEvent.DISCOVER,
#            self._handler_connected_discover)

    def _handler_connected_discover(self, event, *args, **kwargs):
        # Redefine discover handler so that we can apply startup params
        # when we discover. Gotta get into command mode first though.
        result = SingleConnectionInstrumentDriver._handler_connected_protocol_event(self, event, *args, **kwargs)
        self.apply_startup_params()
        return result


###############################################################################
# Protocol
###############################################################################

class SeaBirdProtocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class for seabird driver.
    Subclasses CommandResponseInstrumentProtocol
    """

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The sbe26plus newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

    ########################################################################
    # Private helpers.
    ########################################################################

    def _sync_clock(self, date_time_param, prompts, timeout, delay=1):
        """
        Send the command to the instrument to syncronize the clock
        @param date_time_param: date time parameter that we want to set
        @param prompts: expected prompt
        @param timeout: command timeout
        @param delay: wakeup delay
        @return: true if the command is successful
        @raise: InstrumentProtocolException if command fails
        """
        prompt = self._wakeup(timeout=timeout, delay=delay)

        # lets clear out any past data so it doesnt confuse the command
        self._linebuf = ''
        self._promptbuf = ''

        str_val = self._param_dict.format(date_time_param, get_timestamp_delayed("%d %b %Y %H:%M:%S"))
        set_cmd = '%s=%s' % (date_time_param, str_val) + NEWLINE

        self._do_cmd_direct(set_cmd)
        (prompt, response) = self._get_response()

        if response != set_cmd + prompt:
            raise InstrumentProtocolException("_clock_sync - response != set_cmd")

        if prompt != prompt:
            raise InstrumentProtocolException("_clock_sync - prompt != Prompt.COMMAND")

        return True

