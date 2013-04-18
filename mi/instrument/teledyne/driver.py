from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol

import time
import datetime as dt
from mi.core.time import get_timestamp_delayed
from mi.core.exceptions import InstrumentParameterException
from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.common import BaseEnum

# default timeout.
TIMEOUT = 20

class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """
    COMMAND = '\r\n>\r\n>'
    #AUTOSAMPLE = ''
    ERR = 'ERR:'
    # POWERING DOWN MESSAGE 
    # "Powering Down"

class TeledyneInstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver Family SubClass
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
        log.debug("in TeledyneInstrumentDriver._handler_connected_discover calling SingleConnectionInstrumentDriver._handler_connected_protocol_event")
        result = SingleConnectionInstrumentDriver._handler_connected_protocol_event(self, event, *args, **kwargs)
        log.debug("in TeledyneInstrumentDriver._handler_connected_discover apply_startup_params")
        self.apply_startup_params()
        return result

class TeledyneProtocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol Family SubClass
    """
    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        log.debug("IN TeledyneProtocol.__init__")
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

    def _sync_clock(self, command, date_time_param, timeout=TIMEOUT, delay=1, time_format="%d %b %Y %H:%M:%S"):
        """
        Send the command to the instrument to syncronize the clock
        @param date_time_param: date time parameter that we want to set
        @param prompts: expected prompt
        @param timeout: command timeout
        @param delay: wakeup delay
        @param time_format: time format string for set command
        @return: true if the command is successful
        @throws: InstrumentProtocolException if command fails
        """
        prompt = self._wakeup(timeout=timeout, delay=delay)

        # lets clear out any past data so it doesnt confuse the command
        self._linebuf = ''
        self._promptbuf = ''

        prompt = self._wakeup(timeout=timeout, delay=delay)
        str_val = get_timestamp_delayed(time_format)
        reply = self._do_cmd_direct(date_time_param + str_val)

        time.sleep(1)
        reply = self._get_response(TIMEOUT)

        return True

    def _apply_params(self):
        """
        apply startup parameters to the instrument.
        @throws: InstrumentProtocolException if in wrong mode.
        """
        log.debug("IN _apply_params")
        config = self.get_startup_config()
        # Pass true to _set_params so we know these are startup values
        self._set_params(config, True)

    def _get_param_result(self, param_list, expire_time):
        """
        return a dictionary of the parameters and values
        @param expire_time: baseline time for expiration calculation
        @return: dictionary of values
        @throws InstrumentParameterException if missing or invalid parameter
        @throws InstrumentParameterExpirationException if value is expired.
        """
        result = {}

        for param in param_list:
            val = self._param_dict.get(param, expire_time)
            result[param] = val

        return result

    ########################################################################
    # Static helpers to format set commands.
    ########################################################################

    @staticmethod
    def _bool_to_int(v):
        """
        Write a bool value to string as an int.
        @param v A bool val.
        @retval a int string.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v, int):
            raise InstrumentParameterException('Value %s is not a int.' % v)
        else:
            if v:
                return 1
            else:
                return 0

    @staticmethod
    def _reverse_bool_to_int(v):
        """
        Write a inverse-bool value to string as an int.
        @param v A bool val.
        @retval a int string.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v, int):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            if v:
                log.debug("RETURNING 0")
                return 0
            else:
                log.debug("RETURNING 1")
                return 1

