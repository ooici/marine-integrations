"""
@package mi.instrument.mclane.ras.ooicore.driver
@file marine-integrations/mi/instrument/mclane/ras/ooicore/driver.py
@author Dan Mergens
@brief Driver for the PPSDN
Release notes:

initial version
"""

__author__ = 'Dan Mergens'
__license__ = 'Apache 2.0'

import re

from mi.core.log import get_logger

log = get_logger()

from mi.core.instrument.instrument_driver import ResourceAgentState

from mi.core.instrument.protocol_param_dict import \
    ProtocolParameterDict, \
    ParameterDictType, \
    ParameterDictVisibility

from mi.instrument.mclane.driver import \
    NEWLINE, \
    McLanePumpConfig, \
    McLaneParameter, \
    McLaneCommand, \
    McLaneResponse, \
    McLaneDataParticleType, \
    McLaneSampleDataParticle, \
    McLaneSampleDataParticleKey, \
    McLaneInstrumentDriver, \
    McLaneProtocol

NUM_PORTS = 24  # number of collection bags

####
#    Driver Constant Definitions
####


class PumpConfig(McLanePumpConfig):
    rate_error_factor = 1.15  # PPS is off in it's flow rate measurement by 14.5%

    default_flush_volume = flush_volume = 150
    default_flush_rate = flush_rate = 100
    default_flush_min_rate = flush_min_rate = 75
    default_fill_volume = fill_volume = 4000
    default_fill_rate = fill_rate = 100
    default_fill_min_rate = fill_min_rate = 75
    default_clear_volume = clear_volume = 100
    default_clear_rate = clear_rate = 100
    default_clear_min_rate = clear_min_rate = 75


class Parameter(McLaneParameter):
    """
    Device specific parameters.
    """
    FLUSH_VOLUME = "PPSFlush_volume"
    FLUSH_FLOWRATE = "PPSFlush_flowrate"
    FLUSH_MINFLOW = "PPSFlush_minflow"
    FILL_VOLUME = "PPSFill_volume"
    FILL_FLOWRATE = "PPSFill_flowrate"
    FILL_MINFLOW = "PPSFill_minflow"
    REVERSE_VOLUME = "PPSReverse_volume"
    REVERSE_FLOWRATE = "PPSReverse_flowrate"
    REVERSE_MINFLOW = "PPSReverse_minflow"


class Command(McLaneCommand):
    """
    Instrument command strings - case insensitive
    """
    CAPACITY = 'capacity'  # pump max flow rate mL/min


class Response(McLaneResponse):
    """
    Expected device response strings
    """
    # e.g. 03/25/14 20:24:02 PPS ML13003-01>
    READY = re.compile(r'(\d+/\d+/\d+\s+\d+:\d+:\d+\s+)PPS (.*)>')
    # Result 00 |  75 100  25   4 |  77.2  98.5  99.1  47 031514 001813 | 29.8 1
    # Result 00 |  10 100  75  60 |  10.0  85.5 100.0   7 032814 193855 | 30.0 1
    PUMP = re.compile(r'(Status|Result).*(\d+)' + NEWLINE)
    # Battery: 30.1V [Alkaline, 18V minimum]
    BATTERY = re.compile(r'Battery:\s+(\d*\.\d+)V\s+\[.*\]')  # battery voltage
    # Capacity: Maxon 250mL
    CAPACITY = re.compile(r'Capacity:\s(Maxon|Pittman)\s+(\d+)mL')  # pump make and capacity
    # McLane Research Laboratories, Inc.
    # CF2 Adaptive Water Transfer System
    # Version 2.02  of Jun  7 2013 18:17
    #  Configured for: Maxon 250ml pump
    VERSION = re.compile(
        r'McLane .*$' + NEWLINE +
        r'CF2 .*$' + NEWLINE +
        r'Version\s+(\S+)\s+of\s+(.*)$' + NEWLINE +  # version and release date
        r'.*$'
    )


#####
# Codes for pump termination

class DataParticleType(McLaneDataParticleType):
    """
    Data particle types produced by this driver
    """
    # TODO - define which commands will be published to user
    PPSDN_PARSED = 'ppsdn_parsed'
    PUMP_STATUS = 'ppsdn_pump_status'
    VOLTAGE_STATUS = 'ppsdn_battery'
    VERSION_INFO = 'ppsdn_version'


###############################################################################
# Data Particles
###############################################################################

class PPSDNSampleDataParticleKey(McLaneSampleDataParticleKey):
    PUMP_STATUS = 'pump_status'
    PORT = 'port'
    VOLUME_COMMANDED = 'volume_commanded'
    FLOW_RATE_COMMANDED = 'flow_rate_commanded'
    MIN_FLOW_COMMANDED = 'min_flow_commanded'
    TIME_LIMIT = 'time_limit'
    VOLUME_ACTUAL = 'volume'
    FLOW_RATE_ACTUAL = 'flow_rate'
    MIN_FLOW_ACTUAL = 'min_flow'
    TIMER = 'elapsed_time'
    DATE = 'date'
    TIME = 'time_of_day'
    BATTERY = 'battery_voltage'
    CODE = 'code'


# data particle for forward, reverse, and result commands
#  e.g.:
#                      --- command ---   -------- result -------------
#     Result port  |  vol flow minf tlim  |  vol flow minf secs date-time  |  batt code
#        Status 00 |  75 100  25   4 |   1.5  90.7  90.7*  1 031514 001727 | 29.9 0
class PPSDNSampleDataParticle(McLaneSampleDataParticle):
    _data_particle_type = DataParticleType.PPSDN_PARSED


###############################################################################
# Driver
###############################################################################

class InstrumentDriver(McLaneInstrumentDriver):
    """
    InstrumentDriver subclass
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    def __init__(self, evt_callback):
        McLaneInstrumentDriver.__init__(self, evt_callback)


###########################################################################
# Protocol
###########################################################################

# noinspection PyMethodMayBeStatic,PyUnusedLocal
class Protocol(McLaneProtocol):
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
        McLaneProtocol.__init__(self, prompts, newline, driver_event)

        # TODO - reset next_port on mechanical refresh of the PPS filters - how is the driver notified?
        # TODO - need to persist state for next_port to save driver restart
        self.next_port = 1  # next available port

    def _handler_command_status(self, *args, **kwargs):
        # get the following:
        # - VERSION
        # - CAPACITY (pump flow)
        # - BATTERY
        # - CODES (termination codes)
        # - COPYRIGHT (termination codes)
        return None, ResourceAgentState.COMMAND

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with XR-420 parameters.
        For each parameter key add value formatting function for set commands.
        """
        # The parameter dictionary.
        self._param_dict = ProtocolParameterDict()

        # Add parameter handlers to parameter dictionary for instrument configuration parameters.
        self._param_dict.add(Parameter.FLUSH_VOLUME,
                             r'Flush Volume: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             # default_value=150,
                             default_value=10,  # djm - fast test value
                             units='mL',
                             startup_param=True,
                             display_name="flush_volume",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FLUSH_FLOWRATE,
                             r'Flush Flow Rate: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=100,
                             units='mL/sec',
                             startup_param=True,
                             display_name="flush_flow_rate",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FLUSH_MINFLOW,
                             r'Flush Min Flow: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=75,
                             units='mL/sec',
                             startup_param=True,
                             display_name="flush_min_flow",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FILL_VOLUME,
                             r'Fill Volume: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             # default_value=4000,
                             default_value=10,  # djm - fast test value
                             units='mL',
                             startup_param=True,
                             display_name="fill_volume",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FILL_FLOWRATE,
                             r'Fill Flow Rate: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=100,
                             units='mL/sec',
                             startup_param=True,
                             display_name="fill_flow_rate",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FILL_MINFLOW,
                             r'Fill Min Flow: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=75,
                             units='mL/sec',
                             startup_param=True,
                             display_name="fill_min_flow",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.REVERSE_VOLUME,
                             r'Reverse Volume: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             # default_value=100,
                             default_value=10,  # djm - fast test value
                             units='mL',
                             startup_param=True,
                             display_name="reverse_volume",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.REVERSE_FLOWRATE,
                             r'Reverse Flow Rate: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=100,
                             units='mL/sec',
                             startup_param=True,
                             display_name="reverse_flow_rate",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.REVERSE_MINFLOW,
                             r'Reverse Min Flow: (.*)V',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=75,
                             units='mL/sec',
                             startup_param=True,
                             display_name="reverse_min_flow",
                             visibility=ParameterDictVisibility.IMMUTABLE)
