"""
@package mi.instrument.sunburst.sami2_pco2.driver
@file marine-integrations/mi/instrument/sunburst/sami2_pco2/driver.py
@author Christopher Wingard
@brief Driver for the Sunburst Sensors, SAMI2-PCO2 (PCO2W)
Release notes:
    Sunburst Sensors SAMI2-PCO2 pCO2 underwater sensor.
    Derived from initial code developed by Chris Center,
    and merged with a base class covering both the PCO2W
    and PHSEN instrument classes.
"""

__author__ = 'Kevin Stiemke'
__license__ = 'Apache 2.0'

import re
import time

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import NotImplementedException

from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.instrument.sunburst.driver import SamiDataParticleType
from mi.instrument.sunburst.driver import SamiParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.instrument.sunburst.driver import Prompt
from mi.instrument.sunburst.driver import SamiInstrumentCommand
from mi.instrument.sunburst.driver import SamiRegularStatusDataParticle
from mi.instrument.sunburst.driver import SamiRegularStatusDataParticleKey
from mi.instrument.sunburst.driver import SamiControlRecordDataParticle
from mi.instrument.sunburst.driver import SamiControlRecordDataParticleKey
from mi.instrument.sunburst.driver import SamiConfigDataParticleKey
from mi.instrument.sunburst.driver import SamiInstrumentDriver
from mi.instrument.sunburst.driver import SamiProtocol
from mi.instrument.sunburst.driver import REGULAR_STATUS_REGEX_MATCHER
from mi.instrument.sunburst.driver import CONTROL_RECORD_REGEX_MATCHER
from mi.instrument.sunburst.driver import ERROR_REGEX_MATCHER
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.instrument.sunburst.driver import NEWLINE
from mi.instrument.sunburst.driver import SamiScheduledJob
from mi.instrument.sunburst.driver import SamiProtocolState
from mi.instrument.sunburst.driver import SamiProtocolEvent
from mi.instrument.sunburst.driver import SamiCapability
from mi.instrument.sunburst.driver import TIMEOUT
from mi.instrument.sunburst.driver import NEW_LINE_REGEX_MATCHER


###
#    Driver Constant Definitions
###

PUMP_REAGENT = '01'  # Pump on, valve off
PUMP_DEIONIZED_WATER = '03'  # Pump on, valve on
PUMP_DURATION_UNITS = 0.125  # 1/8 second

# Imported from base class

###
#    Driver RegEx Definitions
###

# Mostly defined in base class with these additional, instrument specific
# additions

# SAMI Sample Records (Types 0x04 or 0x05)
SAMI_SAMPLE_REGEX = (
    r'[\*]' +  # record identifier
    '([0-9A-Fa-f]{2})' +  # unique instrument identifier
    '([0-9A-Fa-f]{2})' +  # length of data record (bytes)
    '(04|05)' +  # type of data record (04 for measurement, 05 for blank)
    '([0-9A-Fa-f]{8})' +  # timestamp (seconds since 1904)
    '([0-9A-Fa-f]{56})' +  # 14 sets of light measurements (counts)
    '([0-9A-Fa-f]{4})' +  # battery voltage (counts)
    '([0-9A-Fa-f]{4})' +  # thermistor (counts)
    '([0-9A-Fa-f]{2})' +  # checksum
    NEWLINE)
SAMI_SAMPLE_REGEX_MATCHER = re.compile(SAMI_SAMPLE_REGEX)

###
#    Begin Classes
###

class ScheduledJob(SamiScheduledJob):
    """
    Extend base class with instrument specific functionality.
    """
    pass

class Pco2wProtocolState(SamiProtocolState):
    """
    Extend base class with instrument specific functionality.
    """
    POLLED_BLANK_SAMPLE = 'PROTOCOL_STATE_POLLED_BLANK_SAMPLE'
    SCHEDULED_BLANK_SAMPLE = 'PROTOCOL_STATE_SCHEDULED_BLANK_SAMPLE'
    DEIONIZED_WATER_FLUSH = 'PROTOCOL_STATE_DEIONIZED_WATER_FLUSH'
    REAGENT_FLUSH = 'PROTOCOL_STATE_REAGENT_FLUSH'

class Pco2wProtocolEvent(SamiProtocolEvent):
    """
    Extend base class with instrument specific functionality.
    """
    ACQUIRE_BLANK_SAMPLE = 'DRIVER_EVENT_ACQUIRE_BLANK_SAMPLE'
    DEIONIZED_WATER_FLUSH = 'DRIVER_EVENT_DEIONIZED_WATER_FLUSH'
    REAGENT_FLUSH = 'DRIVER_EVENT_REAGENT_FLUSH'

    EXECUTE_FLUSH = 'PROTOCOL_EVENT_EXECUTE_FLUSH'

class Pco2wCapability(SamiCapability):
    """
    Extend base class with instrument specific functionality.
    """
    ACQUIRE_BLANK_SAMPLE = Pco2wProtocolEvent.ACQUIRE_BLANK_SAMPLE
    DEIONIZED_WATER_FLUSH = Pco2wProtocolEvent.DEIONIZED_WATER_FLUSH
    REAGENT_FLUSH = Pco2wProtocolEvent.REAGENT_FLUSH

class Pco2wSamiDataParticleType(SamiDataParticleType):
    """
    Extend base class with instrument specific functionality.
    """
    SAMI_SAMPLE = 'pco2w_sami_data_record'

class Pco2wSamiParameter(SamiParameter):
    """
    Device specific parameters.
    """

    # PCO2W driver extends the base class (SamiParameter) with:
    PUMP_PULSE = 'pump_pulse'
    PUMP_DURATION = 'pump_duration'
    SAMPLES_PER_MEASUREMENT = 'samples_per_measurement'
    CYCLES_BETWEEN_BLANKS = 'cycles_between_blanks'
    NUMBER_REAGENT_CYCLES = 'number_reagent_cycles'
    NUMBER_BLANK_CYCLES = 'number_blank_cycles'
    FLUSH_PUMP_INTERVAL = 'flush_pump_interval'
    BIT_SWITCHES = 'bit_switches'
    NUMBER_EXTRA_PUMP_CYCLES = 'number_extra_pump_cycles'

    FLUSH_DURATION = 'flush_duration'

class Pco2wInstrumentCommand(SamiInstrumentCommand):
    """
    Extend base class with instrument specific functionality.
    """
    ACQUIRE_BLANK_SAMPLE_SAMI = 'C'

    PUMP_DEIONIZED_WATER_SAMI = 'P' + PUMP_DEIONIZED_WATER
    PUMP_REAGENT_SAMI = 'P' + PUMP_REAGENT
    PUMP_OFF = 'P'

###############################################################################
# Data Particles
###############################################################################
class Pco2wSamiSampleDataParticleKey(BaseEnum):
    """
    Data particle key for the SAMI2-PCO2 records. These particles
    capture when a sample was processed.
    """

    UNIQUE_ID = 'unique_id'
    RECORD_LENGTH = 'record_length'
    RECORD_TYPE = 'record_type'
    RECORD_TIME = 'record_time'
    LIGHT_MEASUREMENTS = 'light_measurements'
    VOLTAGE_BATTERY = 'voltage_battery'
    THERMISTER_RAW = 'thermistor_raw'
    CHECKSUM = 'checksum'


class Pco2wSamiSampleDataParticle(DataParticle):
    """
    Routines for parsing raw data into a SAMI2-PCO2 sample data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """

    _data_particle_type = Pco2wSamiDataParticleType.SAMI_SAMPLE

    def _build_parsed_values(self):
        """
        Parse SAMI2-PCO2 measurement records from raw data into a dictionary
        """

        ### SAMI Sample Record
        # Regular SAMI (PCO2) data records produced by the instrument on either
        # command or via an internal schedule. Like the control records, the
        # messages are preceded by a '*' character and terminated with a '\r'.
        # Sample string:
        #
        #   *542705CEE91CC800400019096206800730074C2CE04274003B0018096106800732074E0D82066124
        #
        # A full description of the data record strings can be found in the
        # vendor supplied SAMI Record Format document.
        ###

        matched = SAMI_SAMPLE_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [Pco2wSamiSampleDataParticleKey.UNIQUE_ID,
                         Pco2wSamiSampleDataParticleKey.RECORD_LENGTH,
                         Pco2wSamiSampleDataParticleKey.RECORD_TYPE,
                         Pco2wSamiSampleDataParticleKey.RECORD_TIME,
                         Pco2wSamiSampleDataParticleKey.LIGHT_MEASUREMENTS,
                         Pco2wSamiSampleDataParticleKey.VOLTAGE_BATTERY,
                         Pco2wSamiSampleDataParticleKey.THERMISTER_RAW,
                         Pco2wSamiSampleDataParticleKey.CHECKSUM]

        result = []
        grp_index = 1

        for key in particle_keys:
            if key in [Pco2wSamiSampleDataParticleKey.LIGHT_MEASUREMENTS]:
                # parse group 5 into 14, 2 byte (4 character) values stored in
                # an array.
                light = matched.group(grp_index)
                light = [int(light[i:i+4], 16) for i in range(0, len(light), 4)]
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: light})
            else:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
            grp_index += 1

        return result

class Pco2wSamiConfigurationDataParticleKey(SamiConfigDataParticleKey):
    """
    Data particle key for the configuration record.
    """

    PUMP_PULSE = 'pump_pulse'
    PUMP_DURATION = 'pump_on_to_measure'
    SAMPLES_PER_MEASUREMENT = 'samples_per_measure'
    CYCLES_BETWEEN_BLANKS = 'cycles_between_blanks'
    NUMBER_REAGENT_CYCLES = 'num_reagent_cycles'
    NUMBER_BLANK_CYCLES = 'num_blank_cycles'
    FLUSH_PUMP_INTERVAL = 'flush_pump_interval'
    DISABLE_START_BLANK_FLUSH = 'disable_start_blank_flush'
    MEASURE_AFTER_PUMP_PULSE = 'measure_after_pump_pulse'
    NUMBER_EXTRA_PUMP_CYCLES = 'cycle_rate'

###############################################################################
# Driver
###############################################################################
class Pco2wInstrumentDriver(SamiInstrumentDriver):
    """
    InstrumentDriver subclass.
    Subclasses SamiInstrumentDriver and SingleConnectionInstrumentDriver with
    connection state machine.
    """

###########################################################################
# Protocol
###########################################################################
class Pco2wProtocol(SamiProtocol):
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

        log.debug('Pco2wProtocol.__init__()')

        # Construct protocol superclass.
        SamiProtocol.__init__(self, prompts, newline, driver_event)

        self._protocol_fsm.add_handler(
            Pco2wProtocolState.COMMAND, Pco2wProtocolEvent.ACQUIRE_BLANK_SAMPLE,
            self._handler_command_acquire_blank_sample)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.COMMAND, Pco2wProtocolEvent.DEIONIZED_WATER_FLUSH,
            self._handler_command_deionized_water_flush)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.COMMAND, Pco2wProtocolEvent.REAGENT_FLUSH,
            self._handler_command_reagent_flush)

        self._protocol_fsm.add_handler(
            Pco2wProtocolState.AUTOSAMPLE, Pco2wProtocolEvent.ACQUIRE_BLANK_SAMPLE,
            self._handler_autosample_acquire_blank_sample)

        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_SAMPLE, Pco2wProtocolEvent.ACQUIRE_BLANK_SAMPLE,
            self._handler_queue_acquire_blank_sample)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_SAMPLE, Pco2wProtocolEvent.ACQUIRE_BLANK_SAMPLE,
            self._handler_queue_acquire_blank_sample)

        # this state would be entered whenever an ACQUIRE_BLANK_SAMPLE event
        # occurred while in the COMMAND state
        # and will last anywhere from a few seconds to 3
        # minutes depending on instrument and sample type.
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.ENTER,
            self._handler_polled_blank_sample_enter)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.EXIT,
            self._handler_polled_blank_sample_exit)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.TAKE_SAMPLE,
            self._handler_take_blank_sample)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.SUCCESS,
            self._handler_polled_blank_sample_success)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.TIMEOUT,
            self._handler_polled_blank_sample_timeout)
        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.ACQUIRE_STATUS,
            self._handler_queue_acquire_status)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.ACQUIRE_SAMPLE,
            self._handler_queue_acquire_sample)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.ACQUIRE_BLANK_SAMPLE,
            self._handler_queue_acquire_blank_sample)

        # this state would be entered whenever an ACQUIRE_BLANK_SAMPLE event
        # occurred while in the AUTOSAMPLE state
        # and will last anywhere from a few seconds to 3
        # minutes depending on instrument and sample type.
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.ENTER,
            self._handler_scheduled_blank_sample_enter)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.EXIT,
            self._handler_scheduled_blank_sample_exit)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.TAKE_SAMPLE,
            self._handler_take_blank_sample)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.SUCCESS,
            self._handler_scheduled_blank_sample_success)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.TIMEOUT,
            self._handler_scheduled_blank_sample_timeout)
        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.ACQUIRE_STATUS,
            self._handler_queue_acquire_status)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.ACQUIRE_SAMPLE,
            self._handler_queue_acquire_sample)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.ACQUIRE_BLANK_SAMPLE,
            self._handler_queue_acquire_blank_sample)

        # this state would be entered whenever a PUMP_DEIONIZED_WATER event
        # occurred while in the COMMAND state
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH, Pco2wProtocolEvent.ENTER,
            self._handler_deionized_water_flush_enter)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH, Pco2wProtocolEvent.EXIT,
            self._handler_deionized_water_flush_exit)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH, Pco2wProtocolEvent.EXECUTE_FLUSH,
            self._handler_deionized_water_flush_execute)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH, Pco2wProtocolEvent.SUCCESS,
            self._handler_deionized_water_flush_success)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH, Pco2wProtocolEvent.TIMEOUT,
            self._handler_deionized_water_flush_timeout)
        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH, Pco2wProtocolEvent.ACQUIRE_STATUS,
            self._handler_queue_acquire_status)

        # this state would be entered whenever a PUMP_REAGENT event
        # occurred while in the COMMAND state
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.REAGENT_FLUSH, Pco2wProtocolEvent.ENTER,
            self._handler_reagent_flush_enter)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.REAGENT_FLUSH, Pco2wProtocolEvent.EXIT,
            self._handler_reagent_flush_exit)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.REAGENT_FLUSH, Pco2wProtocolEvent.EXECUTE_FLUSH,
            self._handler_reagent_flush_execute)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.REAGENT_FLUSH, Pco2wProtocolEvent.SUCCESS,
            self._handler_reagent_flush_success)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.REAGENT_FLUSH, Pco2wProtocolEvent.TIMEOUT,
            self._handler_reagent_flush_timeout)
        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.REAGENT_FLUSH, Pco2wProtocolEvent.ACQUIRE_STATUS,
            self._handler_queue_acquire_status)

        self._add_build_handler(Pco2wInstrumentCommand.ACQUIRE_BLANK_SAMPLE_SAMI, self._build_simple_command)
        self._add_build_handler(Pco2wInstrumentCommand.PUMP_DEIONIZED_WATER_SAMI, self._build_pump_command)
        self._add_build_handler(Pco2wInstrumentCommand.PUMP_REAGENT_SAMI, self._build_pump_command)
        self._add_build_handler(Pco2wInstrumentCommand.PUMP_OFF, self._build_simple_command)

        # Add response handlers for device commands.
        self._add_response_handler(Pco2wInstrumentCommand.ACQUIRE_BLANK_SAMPLE_SAMI, self._parse_response_blank_sample_sami)
        self._add_response_handler(Pco2wInstrumentCommand.PUMP_DEIONIZED_WATER_SAMI, self._parse_response_pump_deionized_water_sami)
        self._add_response_handler(Pco2wInstrumentCommand.PUMP_REAGENT_SAMI, self._parse_response_pump_reagent_sami)
        self._add_response_handler(Pco2wInstrumentCommand.PUMP_OFF, self._parse_response_pump_off_sami)

        self._engineering_parameters.append(Pco2wSamiParameter.FLUSH_DURATION)

    ########################################################################
    # Build command handlers.
    ########################################################################

    def _build_pump_command(self, cmd):

        param = Pco2wSamiParameter.FLUSH_DURATION
        value = self._param_dict.get(param)
        flush_duration_str = self._param_dict.format(param, value)

        log.debug('Pco2wProtocol._build_pump_command(): flush duration value = %s, string = %s' % (value, flush_duration_str))

        pump_command = cmd + flush_duration_str + NEWLINE

        log.debug('Pco2wProtocol._build_pump_command(): pump command = %s' % pump_command)

        return pump_command

    ########################################################################
    # Events to queue handlers.
    ########################################################################
    def _handler_queue_acquire_blank_sample(self, *args, **kwargs):
        """
        Buffer blank sample command received during taking a sample
        """
        log.debug('Pco2wProtocol._handler_queue_acquire_blank_sample():' +
                  ' queueing Pco2wProtocolEvent.ACQUIRE_BLANK_SAMPLE in state ' +
                  self.get_current_state())

        self._queued_commands.sample = Pco2wProtocolEvent.ACQUIRE_BLANK_SAMPLE

        next_state = None
        next_agent_state = None
        result = None

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_acquire_blank_sample(self):
        """
        Acquire a blank sample
        """

        log.debug('Pco2wProtocol._handler_command_acquire_blank_sample()')

        next_state = Pco2wProtocolState.POLLED_BLANK_SAMPLE
        next_agent_state = ResourceAgentState.BUSY
        result = None

        return (next_state, (next_agent_state, result))

    def _handler_command_deionized_water_flush(self):
        """
        Flush with deionized water
        """

        log.debug('Pco2wProtocol._handler_command_deionized_water_flush()')

        next_state = Pco2wProtocolState.DEIONIZED_WATER_FLUSH
        next_agent_state = ResourceAgentState.BUSY
        result = None

        return (next_state, (next_agent_state, result))

    def _handler_command_reagent_flush(self):
        """
        Flush with reagent
        """

        log.debug('Pco2wProtocol._handler_command_reagent_flush()')

        next_state = Pco2wProtocolState.REAGENT_FLUSH
        next_agent_state = ResourceAgentState.BUSY
        result = None

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Deionized water flush handlers.
    ########################################################################

    def _handler_deionized_water_flush_enter(self, *args, **kwargs):
        """
        Enter state.
        """

        log.debug('Pco2wProtocol._handler_deionized_water_flush_enter')

        self._async_raise_fsm_event(Pco2wProtocolEvent.EXECUTE_FLUSH)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_deionized_water_flush_exit(self, *args, **kwargs):
        """
        Exit state.
        """

        log.debug('Pco2wProtocol._handler_deionized_water_flush_exit')

    def _handler_deionized_water_flush_success(self, *args, **kwargs):
        """
        Successfully received a sample from SAMI
        """

        log.debug('Pco2wProtocol._handler_deionized_water_flush_success')

        next_state = Pco2wProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        self._async_agent_state_change(next_agent_state)

        return (next_state, next_agent_state)

    def _handler_deionized_water_flush_timeout(self, *args, **kwargs):
        """
        Sample timeout occurred.
        """

        log.error('Pco2wProtocol._handler_deionized_water_flush_timeout(): Deionized water flush timeout occurred')

        next_state = Pco2wProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        self._async_agent_state_change(next_agent_state)

        return (next_state, next_agent_state)

    def _handler_deionized_water_flush_execute(self, *args, **kwargs):
        """
        Execute pump command, sleep to make sure it completes and make sure pump is off
        """

        try:
            flush_duration = self._param_dict.get(Pco2wSamiParameter.FLUSH_DURATION)
            flush_duration_seconds = flush_duration * PUMP_DURATION_UNITS

            log.debug('Pco2wProtocol._handler_deionized_water_flush_execute(): flush duration param = %s, seconds = %s' % (flush_duration, flush_duration_seconds))

            # Add 1 seconds to make sure pump completes.

            flush_duration_seconds += 1.0

            log.debug('Pco2wProtocol._handler_deionized_water_flush_execute(): sleeping %f seconds' % flush_duration_seconds)

            self._do_cmd_resp(Pco2wInstrumentCommand.PUMP_DEIONIZED_WATER_SAMI, timeout=TIMEOUT, response_regex=NEW_LINE_REGEX_MATCHER)

            time.sleep(flush_duration_seconds)

            # Make sure pump is off

            self._do_cmd_resp(Pco2wInstrumentCommand.PUMP_OFF, timeout=TIMEOUT, response_regex=NEW_LINE_REGEX_MATCHER)

            log.debug('Pco2wProtocol._handler_deionized_water_flush_execute(): SUCCESS')

            self._async_raise_fsm_event(Pco2wProtocolEvent.SUCCESS)
        except InstrumentTimeoutException:
            log.error('Pco2wProtocol._handler_deionized_water_flush_execute(): TIMEOUT')
            self._async_raise_fsm_event(Pco2wProtocolEvent.TIMEOUT)

        return None, None

    ########################################################################
    # Reagent flush handlers.
    ########################################################################

    def _handler_reagent_flush_enter(self, *args, **kwargs):
        """
        Enter state.
        """

        log.debug('Pco2wProtocol._handler_reagent_flush_enter')

        self._async_raise_fsm_event(Pco2wProtocolEvent.EXECUTE_FLUSH)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_reagent_flush_exit(self, *args, **kwargs):
        """
        Exit state.
        """

        log.debug('Pco2wProtocol._handler_reagent_flush_exit')

    def _handler_reagent_flush_success(self, *args, **kwargs):
        """
        Successfully received a sample from SAMI
        """

        log.debug('Pco2wProtocol._handler_reagent_flush_success')

        next_state = Pco2wProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        self._async_agent_state_change(next_agent_state)

        return (next_state, next_agent_state)

    def _handler_reagent_flush_timeout(self, *args, **kwargs):
        """
        Sample timeout occurred.
        """

        log.error('Pco2wProtocol._handler_reagent_flush_timeout(): Reagent flush timeout occurred')

        next_state = Pco2wProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        self._async_agent_state_change(next_agent_state)

        return (next_state, next_agent_state)

    def _handler_reagent_flush_execute(self, *args, **kwargs):
        """
        Execute pump command, sleep to make sure it completes and make sure pump is off
        """

        try:
            flush_duration = self._param_dict.get(Pco2wSamiParameter.FLUSH_DURATION)
            flush_duration_seconds = flush_duration * PUMP_DURATION_UNITS

            log.debug('Pco2wProtocol._handler_reagent_flush_execute(): flush duration param = %s, seconds = %s' % (flush_duration, flush_duration_seconds))

            # Add 1 seconds to make sure pump completes.

            flush_duration_seconds += 1.0

            log.debug('Pco2wProtocol._handler_reagent_flush_execute(): sleeping %f seconds' % flush_duration_seconds)

            self._do_cmd_resp(Pco2wInstrumentCommand.PUMP_REAGENT_SAMI, timeout=TIMEOUT, response_regex=NEW_LINE_REGEX_MATCHER)

            time.sleep(flush_duration_seconds)

            # Make sure pump is off

            self._do_cmd_resp(Pco2wInstrumentCommand.PUMP_OFF, timeout=TIMEOUT, response_regex=NEW_LINE_REGEX_MATCHER)

            log.debug('Pco2wProtocol._handler_reagent_flush_execute(): SUCCESS')
            self._async_raise_fsm_event(Pco2wProtocolEvent.SUCCESS)
        except InstrumentTimeoutException:
            log.error('Pco2wProtocol._handler_reagent_flush_execute(): TIMEOUT')
            self._async_raise_fsm_event(Pco2wProtocolEvent.TIMEOUT)

        return None, None

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_acquire_blank_sample(self, *args, **kwargs):
        """
        While in autosample mode, poll for blank samples
        """

        log.debug('Pco2wProtocol._handler_autosample_acquire_blank_sample')

        next_state = Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE
        next_agent_state = ResourceAgentState.BUSY
        result = None

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Take Blank Sample handler used in sample states
    ########################################################################

    def _handler_take_blank_sample(self, *args, **kwargs):
        """
        Acquire the instrument's status
        """

        log.debug('Pco2wProtocol._handler_take_blank_sample() ENTER')
        log.debug('Pco2wProtocol._handler_take_blank_sample(): CURRENT_STATE == ' + self.get_current_state())

        try:
            self._take_blank_sample()
            log.debug('Pco2wProtocol._handler_take_blank_sample(): SUCCESS')
            self._async_raise_fsm_event(Pco2wProtocolEvent.SUCCESS)
        except InstrumentTimeoutException:
            log.error('Pco2wProtocol._handler_take_blank_sample(): TIMEOUT')
            self._async_raise_fsm_event(Pco2wProtocolEvent.TIMEOUT)

        log.debug('Pco2wProtocol._handler_take_blank_sample() EXIT')

        return None, None

    ########################################################################
    # Polled Blank Sample handlers.
    ########################################################################

    def _handler_polled_blank_sample_enter(self, *args, **kwargs):
        """
        Enter state.
        """

        log.debug('Pco2wProtocol._handler_polled_sample_enter')

        self._async_raise_fsm_event(Pco2wProtocolEvent.TAKE_SAMPLE)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_polled_blank_sample_exit(self, *args, **kwargs):
        """
        Exit state.
        """

        log.debug('Pco2wProtocol._handler_polled_sample_exit')

    def _handler_polled_blank_sample_success(self, *args, **kwargs):
        """
        Successfully received a sample from SAMI
        """

        log.debug('Pco2wProtocol._handler_polled_sample_success')

        next_state = Pco2wProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        self._async_agent_state_change(next_agent_state)

        return (next_state, next_agent_state)

    def _handler_polled_blank_sample_timeout(self, *args, **kwargs):
        """
        Sample timeout occurred.
        """

        log.error('Pco2wProtocol._handler_polled_blank_sample_timeout(): Blank sample timeout occurred')

        next_state = Pco2wProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        self._async_agent_state_change(next_agent_state)

        return (next_state, next_agent_state)

    ########################################################################
    # Scheduled Blank Sample handlers.
    ########################################################################

    def _handler_scheduled_blank_sample_enter(self, *args, **kwargs):
        """
        Enter state.
        """

        log.debug('Pco2wProtocol._handler_scheduled_blank_sample_enter')

        self._async_raise_fsm_event(Pco2wProtocolEvent.TAKE_SAMPLE)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_scheduled_blank_sample_exit(self, *args, **kwargs):
        """
        Exit state.
        """

        log.debug('Pco2wProtocol._handler_scheduled_blank_sample_exit')

    def _handler_scheduled_blank_sample_success(self, *args, **kwargs):
        """
        Successfully received a sample from SAMI
        """

        log.debug('Pco2wProtocol._handler_scheduled_blank_sample_success')

        next_state = Pco2wProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        self._async_agent_state_change(next_agent_state)

        return (next_state, next_agent_state)

    def _handler_scheduled_blank_sample_timeout(self, *args, **kwargs):
        """
        Sample timeout occurred.
        """

        log.error('Pco2wProtocol._handler_scheduled_blank_sample_timeout(): Blank sample timeout occurred')

        next_state = Pco2wProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        self._async_agent_state_change(next_agent_state)

        return (next_state, next_agent_state)

    ########################################################################
    # Response handlers.
    ########################################################################

    def _parse_response_blank_sample_sami(self, response, prompt):
        """
        Parse response to take blank sample instrument command
        """
        log.debug('Pco2wProtocol._parse_response_blank_sample_sami')

    def _parse_response_pump_deionized_water_sami(self, response, prompt):
        """
        Parse response to pump deionized water command
        """
        log.debug('Pco2wProtocol._parse_response_pump_deionized_water_sami')

    def _parse_response_pump_reagent_sami(self, response, prompt):
        """
        Parse response to pump reagent command
        """
        log.debug('Pco2wProtocol._parse_response_pump_reagent_sami')

    def _parse_response_pump_off_sami(self, response, prompt):
        """
        Parse response to pump off command
        """
        log.debug('Pco2wProtocol._parse_response_pump_off_sami')

    ########################################################################
    # Private Methods
    ########################################################################

    def _take_blank_sample(self):
        """
        Take blank sample instrument command
        """

        log.debug('Pco2wProtocol._take_blank_sample(): _take_blank_sample() START')

        self._pre_sample_processing()

        start_time = time.time()

        ## An exception is raised if timeout is hit.
        self._do_cmd_resp(Pco2wInstrumentCommand.ACQUIRE_BLANK_SAMPLE_SAMI, timeout = self._get_blank_sample_timeout(), response_regex=self._get_sample_regex())

        sample_time = time.time() - start_time

        log.debug('Pco2wProtocol._take_blank_sample(): Blank Sample took ' + str(sample_time) + ' to FINISH')

    ########################################################################
    # Build Command, Driver and Parameter dictionaries
    ########################################################################

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """

        log.debug('Pco2wProtocol._build_command_dict')

        SamiProtocol._build_command_dict(self)

        self._cmd_dict.add(Pco2wCapability.ACQUIRE_BLANK_SAMPLE, display_name="acquire blank sample")
        self._cmd_dict.add(Pco2wCapability.DEIONIZED_WATER_FLUSH, display_name="deionized water flush")
        self._cmd_dict.add(Pco2wCapability.REAGENT_FLUSH, display_name="reagent flush")

    def _build_param_dict(self):
        """
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """

        log.debug('Pco2wProtocol._build_param_dict()')

        SamiProtocol._build_param_dict(self)

        configuration_string_regex = self._get_configuration_string_regex()

        # PCO2 0x04, PHSEN 0x0A
        self._param_dict.add(Pco2wSamiParameter.SAMI_DRIVER_VERSION, configuration_string_regex,
                             lambda match: int(match.group(6), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x04,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='sami driver version')

        self._param_dict.add(Pco2wSamiParameter.PUMP_PULSE, configuration_string_regex,
                             lambda match: int(match.group(21), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x10,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='pump pulse duration')

        self._param_dict.add(Pco2wSamiParameter.PUMP_DURATION, configuration_string_regex,
                             lambda match: int(match.group(22), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x20,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='pump measurement duration')

        self._param_dict.add(Pco2wSamiParameter.SAMPLES_PER_MEASUREMENT, configuration_string_regex,
                             lambda match: int(match.group(23), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0xFF,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='samples per measurement')

        self._param_dict.add(Pco2wSamiParameter.CYCLES_BETWEEN_BLANKS, configuration_string_regex,
                             lambda match: int(match.group(24), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0xA8,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='cycles between blanks')

        self._param_dict.add(Pco2wSamiParameter.NUMBER_REAGENT_CYCLES, configuration_string_regex,
                             lambda match: int(match.group(25), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x18,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of reagent cycles')

        self._param_dict.add(Pco2wSamiParameter.NUMBER_BLANK_CYCLES, configuration_string_regex,
                             lambda match: int(match.group(26), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x1C,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of blank cycles')

        self._param_dict.add(Pco2wSamiParameter.FLUSH_PUMP_INTERVAL, configuration_string_regex,
                             lambda match: int(match.group(27), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x01,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='flush pump interval')

        self._param_dict.add(Pco2wSamiParameter.BIT_SWITCHES, configuration_string_regex,
                             lambda match: int(match.group(28), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='bit switches')

        self._param_dict.add(Pco2wSamiParameter.NUMBER_EXTRA_PUMP_CYCLES, configuration_string_regex,
                             lambda match: int(match.group(29), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x38,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of extra pump cycles')

        self._param_dict.add(Pco2wSamiParameter.FLUSH_DURATION, r'Flush duration = ([0-9]+)',
                             lambda match: match.group(1),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=False,
                             default_value=1,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='flush duration')

    ########################################################################
    # Overridden base class methods
    ########################################################################


    def _get_blank_sample_timeout(self):
        """
        Overridden by device specific subclasses.
        """

        raise NotImplementedException()

    def _get_sample_regex(self):
        """
        Get sample regex
        @retval sample regex
        """
        log.debug('Protocol._get_sample_regex()')
        return SAMI_SAMPLE_REGEX_MATCHER
