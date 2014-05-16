"""
@package mi.instrument.mclane.ras.ooicore.driver
@file marine-integrations/mi/instrument/mclane/rasfl/ras/driver.py
@author Bill Bollenbacher & Dan Mergens
@brief Driver for the RASFL
Release notes:

initial version
"""
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver

__author__ = 'Bill Bollenbacher & Dan Mergens'
__license__ = 'Apache 2.0'

import re

from mi.core.log import get_logger

log = get_logger()

from mi.core.instrument.protocol_param_dict import \
    ProtocolParameterDict, \
    ParameterDictType, \
    ParameterDictVisibility

from mi.instrument.mclane.driver import \
    NEWLINE, \
    ProtocolEvent, \
    Parameter, \
    Prompt, \
    McLaneCommand, \
    McLaneResponse, \
    McLaneDataParticleType, \
    McLaneSampleDataParticle, \
    McLaneProtocol, \
    ProtocolState

NUM_PORTS = 48  # number of collection bags

####
#    Driver Constant Definitions
####


FLUSH_VOLUME = 150
FLUSH_RATE = 100
FLUSH_MIN_RATE = 25
FILL_VOLUME = 425
FILL_RATE = 75
FILL_MIN_RATE = 25
CLEAR_VOLUME = 75
CLEAR_RATE = 100
CLEAR_MIN_RATE = 25


class Command(McLaneCommand):
    """
    Instrument command strings - case insensitive
    """
    CAPACITY = 'capacity'  # sample collection bag capacity mL


class Response(McLaneResponse):
    """
    Expected device response strings
    """
    # e.g. 03/14/14 20:19:49 RAS ML12881-02>
    READY = re.compile(r'(\d+/\d+/\d+\s+\d+:\d+:\d+\s+)RAS (.*)>')
    # Battery: 29.9V [Alkaline, 18V minimum]
    # Bag capacity: 500
    CAPACITY = re.compile(r'Bag capacity:\s+\d')
    # McLane Research Laboratories, Inc.
    # CF2 Adaptive Remote Sampler
    # Version 3.02 of Jun  6 2013 15:38
    # Pump type: Maxon 125ml
    # Bag capacity: 500
    VERSION = re.compile(
        r'McLane .*$' + NEWLINE +
        r'CF2 .*$' + NEWLINE +
        r'Version\s+(\S+)\s+of\s+(.*)$' + NEWLINE +  # version and release date
        r'Pump type:\s+.*$' +
        r'Bag capacity:\s+\d.*$'
    )


class DataParticleType(McLaneDataParticleType):
    """
    Data particle types produced by this driver
    """
    # TODO - define which commands will be published to user
    RASFL_PARSED = 'rasfl_parsed'


###############################################################################
# Data Particles
###############################################################################

# data particle for forward, reverse, and result commands
#  e.g.:
#                      --- command ---   -------- result -------------
#     Result port  |  vol flow minf tlim  |  vol flow minf secs date-time  |  batt code
#        Status 00 |  75 100  25   4 |   1.5  90.7  90.7*  1 031514 001727 | 29.9 0
class RASFLSampleDataParticle(McLaneSampleDataParticle):
    _data_particle_type = DataParticleType.RASFL_PARSED


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
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################

    @staticmethod
    def get_resource_params():
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
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


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

        # TODO - reset next_port on mechanical refresh of the RAS bags - how is the driver notified?
        # TODO - need to persist state for next_port to save driver restart
        self.next_port = 1  # next available port

        # TODO - on init, perform the following commands:
        # - VERSION
        # - CAPACITY (pump flow)
        # - BATTERY
        # - CODES (termination codes)
        # - COPYRIGHT (termination codes)

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        filling = self.get_current_state() == ProtocolState.FILL
        log.debug("_got_chunk:\n%s", chunk)
        sample_dict = self._extract_sample(RASFLSampleDataParticle,
                                           RASFLSampleDataParticle.regex_compiled(), chunk, timestamp, publish=filling)

        if sample_dict:
            self._linebuf = ''
            self._promptbuf = ''
            self._protocol_fsm.on_event(ProtocolEvent.PUMP_STATUS,
                                        RASFLSampleDataParticle.regex_compiled().search(chunk))

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with XR-420 parameters.
        For each parameter key add value formatting function for set commands.
        """
        # The parameter dictionary.
        self._param_dict = ProtocolParameterDict()

        # Add parameter handlers to parameter dictionary for instrument configuration parameters.
        self._param_dict.add(Parameter.FLUSH_VOLUME,
                             r'Flush Volume: (.*)mL',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=FLUSH_VOLUME,
                             units='mL',
                             startup_param=True,
                             display_name="flush_volume",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FLUSH_FLOWRATE,
                             r'Flush Flow Rate: (.*)mL/min',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=FLUSH_RATE,
                             units='mL/min',
                             startup_param=True,
                             display_name="flush_flow_rate",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FLUSH_MINFLOW,
                             r'Flush Min Flow: (.*)mL/min',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=FLUSH_MIN_RATE,
                             units='mL/min',
                             startup_param=True,
                             display_name="flush_min_flow",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FILL_VOLUME,
                             r'Fill Volume: (.*)mL',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=FILL_VOLUME,
                             units='mL',
                             startup_param=True,
                             display_name="fill_volume",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FILL_FLOWRATE,
                             r'Fill Flow Rate: (.*)mL/min',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=FILL_RATE,
                             units='mL/min',
                             startup_param=True,
                             display_name="fill_flow_rate",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.FILL_MINFLOW,
                             r'Fill Min Flow: (.*)mL/min',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=FILL_MIN_RATE,
                             units='mL/min',
                             startup_param=True,
                             display_name="fill_min_flow",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.CLEAR_VOLUME,
                             r'Reverse Volume: (.*)mL',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=CLEAR_VOLUME,
                             units='mL',
                             startup_param=True,
                             display_name="clear_volume",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.CLEAR_FLOWRATE,
                             r'Reverse Flow Rate: (.*)mL/min',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=CLEAR_RATE,
                             units='mL/min',
                             startup_param=True,
                             display_name="clear_flow_rate",
                             visibility=ParameterDictVisibility.IMMUTABLE)
        self._param_dict.add(Parameter.CLEAR_MINFLOW,
                             r'Reverse Min Flow: (.*)mL/min',
                             None,
                             self._int_to_string,
                             type=ParameterDictType.INT,
                             default_value=CLEAR_MIN_RATE,
                             units='mL/min',
                             startup_param=True,
                             display_name="clear_min_flow",
                             visibility=ParameterDictVisibility.IMMUTABLE)

        self._param_dict.set_value(Parameter.FLUSH_VOLUME, FLUSH_VOLUME)
        self._param_dict.set_value(Parameter.FLUSH_FLOWRATE, FLUSH_RATE)
        self._param_dict.set_value(Parameter.FLUSH_MINFLOW, FLUSH_MIN_RATE)
        self._param_dict.set_value(Parameter.FILL_VOLUME, FILL_VOLUME)
        self._param_dict.set_value(Parameter.FILL_FLOWRATE, FILL_RATE)
        self._param_dict.set_value(Parameter.FILL_MINFLOW, FILL_MIN_RATE)
        self._param_dict.set_value(Parameter.CLEAR_VOLUME, CLEAR_VOLUME)
        self._param_dict.set_value(Parameter.CLEAR_FLOWRATE, CLEAR_RATE)
        self._param_dict.set_value(Parameter.CLEAR_MINFLOW, CLEAR_MIN_RATE)
