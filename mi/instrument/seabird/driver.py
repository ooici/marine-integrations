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

from mi.core.exceptions import NotImplementedException
from mi.core.instrument.instrument_protocol import DriverProtocolState
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
        self._connection_fsm.add_handler(DriverConnectionState.CONNECTED,
            DriverEvent.DISCOVER,
            self._handler_connected_discover)

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

    def _sync_clock(self, date_time_param, prompts, timeout, delay=1, time_format="%d %b %Y %H:%M:%S"):
        """
        Send the command to the instrument to syncronize the clock
        @param date_time_param: date time parameter that we want to set
        @param prompts: expected prompt
        @param timeout: command timeout
        @param delay: wakeup delay
        @param time_format: time format string for set command
        @return: true if the command is successful
        @raise: InstrumentProtocolException if command fails
        """
        prompt = self._wakeup(timeout=timeout, delay=delay)

        # lets clear out any past data so it doesnt confuse the command
        self._linebuf = ''
        self._promptbuf = ''

        str_val = self._param_dict.format(date_time_param, get_timestamp_delayed(time_format))
        self._set_params({date_time_param: str_val})

        return True

    ########################################################################
    # Startup parameter handlers
    ########################################################################
    def apply_startup_params(self):
        """
        Apply all startup parameters.  First we check the instrument to see
        if we need to set the parameters.  If they are they are set
        correctly then we don't do anything.

        If we need to set parameters then we might need to transition to
        command first.  Then we will transition back when complete.

        @todo: This feels odd.  It feels like some of this logic should
               be handled by the state machine.  It's a pattern that we
               may want to review.  I say this because this command
               needs to be run from autosample or command mode.
        @raise: InstrumentProtocolException if not in command or streaming
        """
        # Let's give it a try in unknown state
        log.debug("CURRENT STATE: %s" % self.get_current_state())
        if (self.get_current_state() != DriverProtocolState.COMMAND and
                    self.get_current_state() != DriverProtocolState.AUTOSAMPLE):
            raise InstrumentProtocolException("Not in command or autosample state. Unable to apply startup params")

        log.debug("sbe apply_startup_params, logging?")
        logging = self._is_logging()
        log.debug("sbe apply_startup_params, logging == %s" % logging)

        # If we are in streaming mode and our configuration on the
        # instrument matches what we think it should be then we
        # don't need to do anything.
        if(not self._instrument_config_dirty()):
            log.debug("configuration not dirty.  Nothing to do here")
            return True

        error = None

        try:
            if(logging):
                # Switch to command mode,
                log.debug("stop logging")
                self._stop_logging()

            log.debug("sbe apply_startup_params now")
            self._apply_params()

        # Catch all error so we can put ourself back into
        # streaming.  Then rethrow the error
        except Exception as e:
            error = e

        finally:
            # Switch back to streaming
            if(logging):
                log.debug("sbe apply_startup_params start logging again")
                self._start_logging()

        if(error):
            raise error

    def _start_logging(self):
        """
        Issue the instrument command to start logging data
        """
        raise NotImplementedException()

    def _stop_logging(self):
        """
        Issue the instrument command to stop logging data
        """
        raise NotImplementedException()

    def _is_logging(self):
        """
        Is the instrument in logging or command mode.
        @return: True if streaming, False if in command, None if we don't know
        """
        raise NotImplementedException()

    def _set_params(self, *args, **kwargs):
        """
        Do the work of sending instrument commands to the instrument to set
        parameters.
        """
        raise NotImplementedException()

    def _update_params(self):
        """
        Send instrument commands to get data to refresh the param_dict cache
        """
        raise NotImplementedException()

    def _apply_params(self):
        """
        apply startup parameters to the instrument.
        @raise: InstrumentProtocolException if in wrong mode.
        """
        config = self.get_startup_config()
        # Pass true to _set_params so we know these are startup values
        self._set_params(config, True)

    def _instrument_config_dirty(self):
        """
        Read the startup config and compare that to what the instrument
        is configured too.  If they differ then return True
        @return: True if the startup config doesn't match the instrument
        @raise: InstrumentParameterException
        """
        # Refresh the param dict cache

        self._update_params()

        startup_params = self._param_dict.get_startup_list()
        log.debug("Startup Parameters: %s" % startup_params)

        for param in startup_params:
            if (self._param_dict.get(param) != self._param_dict.get_config_value(param)):
                log.debug("DIRTY: %s %s != %s" % (param, self._param_dict.get(param), self._param_dict.get_config_value(param)))
                return True

        log.debug("Clean instrument config")
        return False

