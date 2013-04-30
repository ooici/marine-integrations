from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import WorkhorseInstrumentDriver
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import WorkhorseProtocol

from mi.core.log import get_logger ; log = get_logger()
class InstrumentDriver(WorkhorseInstrumentDriver):
    """
    Specialization for this version of the workhorse_monitor_75_khz driver
    """
    pass


class Protocol(WorkhorseProtocol):
    """
    Specialization for this version of the workhorse_monitor_75_khz driver
    """
    pass
