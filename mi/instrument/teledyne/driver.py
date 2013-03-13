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






