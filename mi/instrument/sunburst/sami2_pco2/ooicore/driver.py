"""
@package mi.instrument.sunburst.sami2_pco2.ooicore.driver
@file marine-integrations/mi/instrument/sunburst/sami2_pco2/ooicore/driver.py
@author Christopher Wingard
@brief Driver for the Sunburst Sensors, SAMI2-PCO2 (PCO2W)
Release notes:

Sunburst Sensors SAMI2-PCO2 pCO2 underwater sensor
    Derived from initial code developed by Chris Center
"""

__author__ = 'Christopher Wingard'
__license__ = 'Apache 2.0'

import re
import string
import time
import datetime
import calendar
import sys      # Exceptions
import copy
from threading import RLock

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import FunctionParameter
from mi.core.time import get_timestamp
from mi.core.time import get_timestamp_delayed

# newline.
NEWLINE = '\r'

# default timeout.
TIMEOUT = 10

# Conversion from SAMI time (seconds since 1904-01-01) to POSIX or Unix
# timestamps (seconds since 1970-01-01). Add this value to convert POSIX
# timestamps to SAMI, and subtract for the reverse.
SAMI_EPOCH = 2082844800


###
#    Driver Constant Definitions
###
class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    TEST = DriverProtocolState.TEST
    CALIBRATE = DriverProtocolState.CALIBRATE


class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    CLOCK_SYNC = DriverEvent.CLOCK_SYNC
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    CLOCK_SYNC = ProtocolEvent.CLOCK_SYNC
    ACQUIRE_STATUS  = ProtocolEvent.ACQUIRE_STATUS


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    LAUNCH_TIME = 'launch_time'
    START_TIME_FROM_LAUNCH = 'start_time_from_launch'
    STOP_TIME_FROM_START = 'stop_time_from_start'
    MODE_BITS = 'mode_bits'
    SAMI_SAMPLE_INTERVAL = 'sami_sample_interval'
    SAMI_DRIVER_VERSION = 'sami_driver_version'
    SAMI_PARAMS_POINTER = 'sami_params_pointer'
    DEVICE1_SAMPLE_INTERVAL = 'device1_sample_interval'
    DEVICE1_DRIVER_VERSION = 'device1_driver_version'
    DEVICE1_PARAMS_POINTER = 'device1_params_pointer'
    DEVICE2_SAMPLE_INTERVAL = 'device2_sample_interval'
    DEVICE2_DRIVER_VERSION = 'device2_driver_version'
    DEVICE2_PARAMS_POINTER = 'device2_params_pointer'
    DEVICE3_SAMPLE_INTERVAL = 'device3_sample_interval'
    DEVICE3_DRIVER_VERSION = 'device3_driver_version'
    DEVICE3_PARAMS_POINTER = 'device3_params_pointer'
    PRESTART_SAMPLE_INTERVAL = 'prestart_sample_interval'
    PRESTART_DRIVER_VERSION = 'prestart_driver_version'
    PRESTART_PARAMS_POINTER = 'prestart_params_pointer'
    GLOBAL_CONFIGURATION = 'global_configuration'
    PUMP_PULSE = 'pump_pulse'
    PUMP_DURATION = 'pump_duration'
    SAMPLES_PER_MEASUREMENT = 'samples_per_measurement'
    CYCLES_BETWEEN_BLANKS = 'cycles_between_blanks'
    NUMBER_REAGENT_CYCLES = 'number_reagent_cycles'
    NUMBER_BLANK_CYCLES = 'number_blank_cycles'
    FLUSH_PUMP_INTERVAL = 'flush_pump_interval'
    BIT_SWITCHES = 'bit_switches'
    NUMBER_EXTRA_PUMP_CYCLES = 'number_extra_pump_cycles'
    EXTERNAL_PUMP_SETTINGS = 'external_pump_settings'


class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """


class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """


###############################################################################
# Data Particles
###############################################################################
# Regular Status Strings (produced every 1 Hz or in response to S0 command)
REGULAR_STATUS_REGEX = r'[:]([0-9A-Fa-f]{8})([0-9A-Fa-f]{4})([0-9A-Fa-f]{6})' + \
                       '([0-9A-Fa-f]{6})([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})'
REGULAR_STATUS_REGEX_MATCHER = re.compile(REGULAR_STATUS_REGEX)

# Control Records (Types 0x80 - 0xFF)
CONTROL_RECORD_REGEX = r'[\*]([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([8-9A-Fa-f][0-9A-Fa-f])' + \
                       '([0-9A-Fa-f]{8})([0-9A-Fa-f]{4})([0-9A-Fa-f]{6})' + \
                       '([0-9A-Fa-f]{6})([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})'
CONTROL_RECORD_REGEX_MATCHER = re.compile(CONTROL_RECORD_REGEX)

# SAMI Sample Records (Types 0x04 or 0x05)
SAMI_SAMPLE_REGEX = r'[\*]([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})(04|05)' + \
                    '([0-9A-Fa-f]{2})([0-9A-Fa-f]{56})([0-9A-Fa-f]{4})' + \
                    '([0-9A-Fa-f]{4})([0-9A-Fa-f]{2})'
SAMI_SAMPLE_REGEX_MATCHER = re.compile(SAMI_SAMPLE_REGEX)

# Device 1 Sample Records (Type 0x11)
DEV1_SAMPLE_REGEX = r'[\*]([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})(11)([0-9A-Fa-f]{8}'
DEV1_SAMPLE_REGEX_MATCHER = re.compile(DEV1_SAMPLE_REGEX)

# Configuration Records
CONFIGURATION_REGEX = r'([0-9A-Fa-f]{8})([0-9A-Fa-f]{8})([0-9A-Fa-f]{8})' + \
                      '([0-9A-Fa-f]{2})' + \
                      '([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})' + \
                      '([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})' + \
                      '([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})' + \
                      '([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})' + \
                      '([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})' + \
                      '([0-9A-Fa-f]{2})' + \
                      '([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})' + \
                      '([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})' + \
                      '([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})' + \
                      '([0-9A-Fa-f]{2})' + \
                      '([0-9A-Fa-f]+)'
CONFIGURATION_REGEX_MATCHER = re.compile(CONFIGURATION_REGEX)

# Error records
ERROR_REGEX = r'[?]([0-9A-Fa-f]{2})'
ERROR_REGEX_MATCHER = re.compile(ERROR_REGEX)


class Pco2aAirSampleDataParticleKey(BaseEnum):
    """
    Data particle key for air sample
    """
    DATE_TIME_STRING = "date_time_string"
    BEGIN_MEASUREMENT = "begin_measurement"
    ZERO_A2D = "zero_a2d"
    CURRENT_A2D = "current_a2d"
    MEASURED_AIR_CO2 = "measured_air_co2"
    AVG_IRG_TEMPERATURE = "avg_irga_temperature"
    HUMIDITY = "humidity"
    HUMIDITY_TEMPERATURE = "humidity_temperature"
    GAS_STREAM_PRESSURE = "gas_stream_pressure"
    IRGA_DETECTOR_TEMPERATURE = "irga_detector_temperature"
    IRGA_SOURCE_TEMPERATURE = "irga_source_temperature"


class Pco2aAirSampleDataParticle(DataParticle):
    """
    Routines for parsing raw data into an air sample data particle structure.
    @throw SampleException If there is a problem with sample creation
    """
    _data_particle_type = DataParticleType.AIR_SAMPLE

    def _build_parsed_values(self):
        """
        Parse air sample values from raw data into a dictionary
        """

        matched = AIR_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [Pco2aAirSampleDataParticleKey.DATE_TIME_STRING,
                         Pco2aAirSampleDataParticleKey.BEGIN_MEASUREMENT,
                         Pco2aAirSampleDataParticleKey.ZERO_A2D,
                         Pco2aAirSampleDataParticleKey.CURRENT_A2D,
                         Pco2aAirSampleDataParticleKey.MEASURED_AIR_CO2,
                         Pco2aAirSampleDataParticleKey.AVG_IRG_TEMPERATURE,
                         Pco2aAirSampleDataParticleKey.HUMIDITY,
                         Pco2aAirSampleDataParticleKey.HUMIDITY_TEMPERATURE,
                         Pco2aAirSampleDataParticleKey.GAS_STREAM_PRESSURE,
                         Pco2aAirSampleDataParticleKey.IRGA_DETECTOR_TEMPERATURE,
                         Pco2aAirSampleDataParticleKey.IRGA_SOURCE_TEMPERATURE]

        result = []
        index = 1
        for key in particle_keys:
            if key in [Pco2aAirSampleDataParticleKey.DATE_TIME_STRING,
                       Pco2aAirSampleDataParticleKey.BEGIN_MEASUREMENT]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: matched.group(index)})
            elif key in [Pco2aAirSampleDataParticleKey.ZERO_A2D,
                         Pco2aAirSampleDataParticleKey.CURRENT_A2D,
                         Pco2aAirSampleDataParticleKey.GAS_STREAM_PRESSURE]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(index))})
            else:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: float(matched.group(index))})
            index += 1

        return result

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
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

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
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent,
                            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER, self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT, self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER, self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER, self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT, self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT, self._handler_command_start_direct)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET, self._handler_command_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET, self._handler_command_set)

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

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        #
        self._chunker = StringChunker(Protocol.sieve_function)


    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        return_list = []

        return return_list

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.

    def _got_chunk(self, chunk):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        return [x for x in events if Capability.has(x)]

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
        Discover current state
        @retval (next_state, result)
        """
        return (ProtocolState.COMMAND, ResourceAgentState.IDLE)

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
        #self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """
        next_state = None
        result = None


        return (next_state, result)

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """
        next_state = None
        result = None

        return (next_state, result)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        result = None
        log.debug("_handler_command_start_direct: entering DA mode")
        return (next_state, (next_agent_state, result))

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
        next_agent_state = None

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return (next_state, (next_agent_state, result))

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        next_state = None
        result = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))
