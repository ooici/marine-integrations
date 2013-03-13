from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol

import time
import datetime as dt
from mi.core.exceptions import InstrumentParameterException
from mi.core.log import get_logger ; log = get_logger()

class ADCPInstrumentDriver(SingleConnectionInstrumentDriver):
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

class ADCPProtocol(CommandResponseInstrumentProtocol):
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
        log.debug("IN ADCPProtocol.__init__")
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)







    ########################################################################
    # Static helpers to format set commands.
    ########################################################################

    @staticmethod
    def _string_to_string(v):
        return v

    @staticmethod
    def _bool_to_int(v):
        """
        Write a bool value to string as an int.
        @param v A bool val.
        @retval a int string.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v, int):
            raise InstrumentParameterException('Value %s is not a float.' % v)
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

    @staticmethod
    def _float_to_string(v):
        """
        Write a float value to string.
        @param v a float val.
        @retval a float string formatted.
        @throws InstrumentParameterException if value is not a float.
        """

        if not isinstance(v, float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            return str(v)  # return a simple float

    @staticmethod
    def _time_to_string(v):
        """
        Write a time value to string.
        @param v a time val.
        @retval a time string formatted.
        @throws InstrumentParameterException if value is not a time.
        """

        if not isinstance(v, time):
            raise InstrumentParameterException('Value %s is not a time.' % v)
        else:
            return time.strftime("%H:%M:%S", v)

    @staticmethod
    def _datetime_with_milis_to_time_string_with_milis(v):
        """
        Write a datetime value to string.
        @param v a datetime val.
        @retval a time w/milis string formatted.
        @throws InstrumentParameterException if value is not a datetime.
        """
        log.debug("IN _datetime_with_milis_to_time_string_with_milis")
        if not isinstance(v, dt.datetime):
            raise InstrumentParameterException('Value %s is not a datetime.' % v)
        else:
            return dt.datetime.strftime(v, '%H:%M:%S.%f')

    @staticmethod
    def _datetime_to_TT_datetime_string(v):
        """
        Write a datetime string value to string.
        @param v a datetime string val.
        @retval a time with date string formatted.
        @throws InstrumentParameterException if value is not a datetime.
        """

        if not isinstance(v, str):
            raise InstrumentParameterException('Value %s is not a datetime.' % v)
        else:
            return time.strftime("%Y/%m/%d,%H:%M:%S", time.strptime(v, "%d %b %Y  %H:%M:%S"))

    @staticmethod
    def _datetime_YY_to_string(v):
        """
        Write a time value to string.
        @param v a time val.
        @retval a time with date string formatted.
        @throws InstrumentParameterException if value is not a datetime.
        """

        if not isinstance(v, time):
            raise InstrumentParameterException('Value %s is not a datetime.' % v)
        else:
            return time.strftime("%y/%m/%d,%H:%M:%S", v)
    @staticmethod
    def _datetime_YYYY_to_string(v):
        """
        Write a time value to string.
        @param v a time val.
        @retval a time with date string formatted.
        @throws InstrumentParameterException if value is not a datetime.
        """

        if not isinstance(v, time):
            raise InstrumentParameterException('Value %s is not a datetime.' % v)
        else:
            return time.strftime("%Y/%m/%d,%H:%M:%S", v)


