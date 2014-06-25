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
from mi.core.exceptions import InstrumentTimeoutException

from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.instrument.sunburst.driver import SamiDataParticleType
from mi.instrument.sunburst.driver import SamiParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.instrument.sunburst.driver import SamiInstrumentCommand
from mi.instrument.sunburst.driver import SamiConfigDataParticleKey
from mi.instrument.sunburst.driver import SamiInstrumentDriver
from mi.instrument.sunburst.driver import SamiProtocol
from mi.instrument.sunburst.driver import SAMI_NEWLINE
from mi.instrument.sunburst.driver import SamiScheduledJob
from mi.instrument.sunburst.driver import SamiProtocolState
from mi.instrument.sunburst.driver import SamiProtocolEvent
from mi.instrument.sunburst.driver import SamiCapability
from mi.instrument.sunburst.driver import SAMI_PUMP_TIMEOUT_OFFSET
from mi.instrument.sunburst.driver import SAMI_PUMP_DURATION_UNITS

###
#    Driver Constant Definitions
###

# PCO2W sample timeout
PCO2W_SAMPLE_TIMEOUT = 180

# Pump on, valve on
PCO2W_PUMP_DEIONIZED_WATER_PARAM = '03'
# Pump on, valve off
PCO2W_PUMP_REAGENT_PARAM = '01'
# 1/8 second increments to pump 50ml
PCO2W_PUMP_DURATION_50ML = 8
# Sleep time between 50ml pumps
PCO2W_PUMP_SLEEP_50ML = 2.0
# Number of times to execute pump for 100ML
PCO2W_PUMP_COMMANDS_50ML = 2

# Imported from base class

###
#    Driver RegEx Definitions
###

# Mostly defined in base class with these additional, instrument specific
# additions

# PCO2W Sample Records (Types 0x04 or 0x05)
PCO2W_SAMPLE_REGEX = (
    r'[\*]' +  # record identifier
    '([0-9A-Fa-f]{2})' +  # unique instrument identifier
    '([0-9A-Fa-f]{2})' +  # length of data record (bytes)
    '(04|05)' +  # type of data record (04 for measurement, 05 for blank)
    '([0-9A-Fa-f]{8})' +  # timestamp (seconds since 1904)
    '([0-9A-Fa-f]{56})' +  # 14 sets of light measurements (counts)
    '([0-9A-Fa-f]{4})' +  # battery voltage (counts)
    '([0-9A-Fa-f]{4})' +  # thermistor (counts)
    '([0-9A-Fa-f]{2})' +  # checksum
    SAMI_NEWLINE)
PCO2W_SAMPLE_REGEX_MATCHER = re.compile(PCO2W_SAMPLE_REGEX)

###
#    Begin Classes
###


class ScheduledJob(SamiScheduledJob):
    """
    Extend base class with instrument specific functionality.
    """


class Pco2wProtocolState(SamiProtocolState):
    """
    Extend base class with instrument specific functionality.
    """
    POLLED_BLANK_SAMPLE = 'PROTOCOL_STATE_POLLED_BLANK_SAMPLE'
    SCHEDULED_BLANK_SAMPLE = 'PROTOCOL_STATE_SCHEDULED_BLANK_SAMPLE'
    DEIONIZED_WATER_FLUSH_100ML = 'PROTOCOL_STATE_DEIONIZED_WATER_FLUSH_100ML'
    REAGENT_FLUSH_100ML = 'PROTOCOL_STATE_REAGENT_FLUSH_100ML'
    DEIONIZED_WATER_FLUSH = 'PROTOCOL_STATE_DEIONIZED_WATER_FLUSH'


class Pco2wProtocolEvent(SamiProtocolEvent):
    """
    Extend base class with instrument specific functionality.
    """
    ACQUIRE_BLANK_SAMPLE = 'DRIVER_EVENT_ACQUIRE_BLANK_SAMPLE'
    DEIONIZED_WATER_FLUSH_100ML = 'DRIVER_EVENT_DEIONIZED_WATER_FLUSH_100ML'
    REAGENT_FLUSH_100ML = 'DRIVER_EVENT_REAGENT_FLUSH_100ML'
    DEIONIZED_WATER_FLUSH = 'DRIVER_EVENT_DEIONIZED_WATER_FLUSH'


class Pco2wCapability(SamiCapability):
    """
    Extend base class with instrument specific functionality.
    """
    ACQUIRE_BLANK_SAMPLE = Pco2wProtocolEvent.ACQUIRE_BLANK_SAMPLE
    DEIONIZED_WATER_FLUSH_100ML = Pco2wProtocolEvent.DEIONIZED_WATER_FLUSH_100ML
    REAGENT_FLUSH_100ML = Pco2wProtocolEvent.REAGENT_FLUSH_100ML
    DEIONIZED_WATER_FLUSH = Pco2wProtocolEvent.DEIONIZED_WATER_FLUSH


class Pco2wSamiDataParticleType(SamiDataParticleType):
    """
    Extend base class with instrument specific functionality.
    """
    SAMI_SAMPLE = 'pco2w_sami_data_record'


class Pco2wParameter(SamiParameter):
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
    PUMP_100ML_CYCLES = 'pump_100ml_cycles'
    DEIONIZED_WATER_FLUSH_DURATION = 'deionized_water_flush_duration'


class Pco2wInstrumentCommand(SamiInstrumentCommand):
    """
    Extend base class with instrument specific functionality.
    """
    PCO2W_ACQUIRE_BLANK_SAMPLE = 'C'
    PCO2W_PUMP_DEIONIZED_WATER = 'P' + PCO2W_PUMP_DEIONIZED_WATER_PARAM
    PCO2W_PUMP_REAGENT = 'P' + PCO2W_PUMP_REAGENT_PARAM


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

        SAMI Sample Record
        Regular SAMI (PCO2) data records produced by the instrument on either
        command or via an internal schedule. Like the control records, the
        messages are preceded by a '*' character and terminated with a '\r'.
        Sample string:

          *542705CEE91CC800400019096206800730074C2CE04274003B0018096106800732074E0D82066124

        A full description of the data record strings can be found in the
        vendor supplied SAMI Record Format document.
        """

        matched = PCO2W_SAMPLE_REGEX_MATCHER.match(self.raw_data)
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
                light = [int(light[i:i + 4], 16) for i in xrange(0, len(light), 4)]
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

        # Construct protocol superclass.
        SamiProtocol.__init__(self, prompts, newline, driver_event)

        self._protocol_fsm.add_handler(
            Pco2wProtocolState.COMMAND, Pco2wProtocolEvent.ACQUIRE_BLANK_SAMPLE,
            self._handler_command_acquire_blank_sample)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.COMMAND, Pco2wProtocolEvent.DEIONIZED_WATER_FLUSH_100ML,
            self._handler_command_deionized_water_flush_100ml)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.COMMAND, Pco2wProtocolEvent.REAGENT_FLUSH_100ML,
            self._handler_command_reagent_flush_100ml)
        self._protocol_fsm.add_handler(
            SamiProtocolState.COMMAND, Pco2wProtocolEvent.DEIONIZED_WATER_FLUSH,
            self._handler_command_deionized_water_flush)

        self._protocol_fsm.add_handler(
            Pco2wProtocolState.AUTOSAMPLE, Pco2wProtocolEvent.ACQUIRE_BLANK_SAMPLE,
            self._handler_autosample_acquire_blank_sample)

        # this state would be entered whenever an ACQUIRE_BLANK_SAMPLE event
        # occurred while in the COMMAND state
        # and will last anywhere from a few seconds to 3
        # minutes depending on instrument and sample type.
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.ENTER,
            self._execution_state_enter)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.EXIT,
            self._execution_state_exit)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.EXECUTE,
            self._handler_take_blank_sample)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.SUCCESS,
            self._execution_success_to_command_state)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.TIMEOUT,
            self._execution_timeout_to_command_state)
        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.POLLED_BLANK_SAMPLE, Pco2wProtocolEvent.ACQUIRE_STATUS,
            self._handler_queue_acquire_status)

        # this state would be entered whenever an ACQUIRE_BLANK_SAMPLE event
        # occurred while in the AUTOSAMPLE state
        # and will last anywhere from a few seconds to 3
        # minutes depending on instrument and sample type.
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.ENTER,
            self._execution_state_enter)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.EXIT,
            self._execution_state_exit)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.EXECUTE,
            self._handler_take_blank_sample)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.SUCCESS,
            self._execution_success_to_autosample_state)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.TIMEOUT,
            self._execution_timeout_to_autosample_state)
        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.SCHEDULED_BLANK_SAMPLE, Pco2wProtocolEvent.ACQUIRE_STATUS,
            self._handler_queue_acquire_status)

        # this state would be entered whenever a DEIONIZED_WATER_FLUSH_100ML event
        # occurred while in the COMMAND state
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH_100ML, Pco2wProtocolEvent.ENTER,
            self._execution_state_enter)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH_100ML, Pco2wProtocolEvent.EXIT,
            self._execution_state_exit)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH_100ML, Pco2wProtocolEvent.EXECUTE,
            self._handler_deionized_water_flush_execute_100ml)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH_100ML, Pco2wProtocolEvent.SUCCESS,
            self._execution_success_to_command_state)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH_100ML, Pco2wProtocolEvent.TIMEOUT,
            self._execution_timeout_to_command_state)
        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH_100ML, Pco2wProtocolEvent.ACQUIRE_STATUS,
            self._handler_queue_acquire_status)

        # this state would be entered whenever a REAGENT_FLUSH_100ML event
        # occurred while in the COMMAND state
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.REAGENT_FLUSH_100ML, Pco2wProtocolEvent.ENTER,
            self._execution_state_enter)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.REAGENT_FLUSH_100ML, Pco2wProtocolEvent.EXIT,
            self._execution_state_exit)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.REAGENT_FLUSH_100ML, Pco2wProtocolEvent.EXECUTE,
            self._handler_reagent_flush_execute_100ml)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.REAGENT_FLUSH_100ML, Pco2wProtocolEvent.SUCCESS,
            self._execution_success_to_command_state)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.REAGENT_FLUSH_100ML, Pco2wProtocolEvent.TIMEOUT,
            self._execution_timeout_to_command_state)
        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.REAGENT_FLUSH_100ML, Pco2wProtocolEvent.ACQUIRE_STATUS,
            self._handler_queue_acquire_status)

        # this state would be entered whenever a DEIONIZED_WATER_FLUSH event
        # occurred while in the COMMAND state
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH, Pco2wProtocolEvent.ENTER,
            self._execution_state_enter)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH, Pco2wProtocolEvent.EXIT,
            self._execution_state_exit)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH, Pco2wProtocolEvent.EXECUTE,
            self._handler_deionized_water_flush_execute)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH, Pco2wProtocolEvent.SUCCESS,
            self._execution_success_to_command_state)
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH, Pco2wProtocolEvent.TIMEOUT,
            self._execution_timeout_to_command_state)
        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            Pco2wProtocolState.DEIONIZED_WATER_FLUSH, Pco2wProtocolEvent.ACQUIRE_STATUS,
            self._handler_queue_acquire_status)

        self._engineering_parameters.append(Pco2wParameter.PUMP_100ML_CYCLES)
        self._engineering_parameters.append(Pco2wParameter.DEIONIZED_WATER_FLUSH_DURATION)

        self._add_build_handler(Pco2wInstrumentCommand.PCO2W_ACQUIRE_BLANK_SAMPLE, self._build_simple_command)
        self._add_build_handler(Pco2wInstrumentCommand.PCO2W_PUMP_DEIONIZED_WATER, self._build_pump_command)
        self._add_build_handler(Pco2wInstrumentCommand.PCO2W_PUMP_REAGENT, self._build_pump_command)

        # Add response handlers for device commands.
        self._add_response_handler(Pco2wInstrumentCommand.PCO2W_ACQUIRE_BLANK_SAMPLE,
                                   self._parse_response_blank_sample_sami)
        self._add_response_handler(Pco2wInstrumentCommand.PCO2W_PUMP_DEIONIZED_WATER,
                                   self._parse_response_newline)
        self._add_response_handler(Pco2wInstrumentCommand.PCO2W_PUMP_REAGENT, self._parse_response_newline)

    ########################################################################
    # Build command handlers.
    ########################################################################

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_acquire_blank_sample(self):
        """
        Acquire a blank sample
        """

        next_state = Pco2wProtocolState.POLLED_BLANK_SAMPLE
        next_agent_state = ResourceAgentState.BUSY
        result = None

        return (next_state, (next_agent_state, result))

    def _handler_command_deionized_water_flush_100ml(self):
        """
        Flush with deionized water
        """

        next_state = Pco2wProtocolState.DEIONIZED_WATER_FLUSH_100ML
        next_agent_state = ResourceAgentState.BUSY
        result = None

        return (next_state, (next_agent_state, result))

    def _handler_command_reagent_flush_100ml(self):
        """
        Flush with reagent
        """

        next_state = Pco2wProtocolState.REAGENT_FLUSH_100ML
        next_agent_state = ResourceAgentState.BUSY
        result = None

        return (next_state, (next_agent_state, result))

    def _handler_command_deionized_water_flush(self):
        """
        Flush with deionized water
        """

        next_state = Pco2wProtocolState.DEIONIZED_WATER_FLUSH
        next_agent_state = ResourceAgentState.BUSY
        result = None

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_acquire_blank_sample(self, *args, **kwargs):
        """
        While in autosample mode, poll for blank samples
        """

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
        log.debug('Pco2wProtocol._handler_take_blank_sample(): CURRENT_STATE == %s', self.get_current_state())

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
    # Deionized water flush 100 ml handlers.
    ########################################################################

    def _handler_deionized_water_flush_execute_100ml(self, *args, **kwargs):
        """
        Execute pump command, sleep to make sure it completes and make sure pump is off
        """

        try:

            pump_100ml_cycles = self._param_dict.get(Pco2wParameter.PUMP_100ML_CYCLES)
            log.debug('Pco2wProtocol._handler_deionized_water_flush_execute_100ml(): pump 100ml cycles = %s',
                      pump_100ml_cycles)

            flush_duration = PCO2W_PUMP_DURATION_50ML
            flush_duration_str = self._param_dict.format(Pco2wParameter.DEIONIZED_WATER_FLUSH_DURATION, flush_duration)
            flush_duration_seconds = flush_duration * SAMI_PUMP_DURATION_UNITS
            log.debug(
                'Pco2wProtocol._handler_deionized_water_flush_execute_100ml(): duration param = %s, seconds = %s',
                flush_duration, flush_duration_seconds)

            # Add offset to timeout make sure pump completes.
            flush_timeout = flush_duration_seconds + SAMI_PUMP_TIMEOUT_OFFSET

            self._execute_pump_sequence(command=Pco2wInstrumentCommand.PCO2W_PUMP_DEIONIZED_WATER,
                                        duration=flush_duration_str,
                                        timeout=flush_timeout,
                                        delay=PCO2W_PUMP_SLEEP_50ML,
                                        command_count=PCO2W_PUMP_COMMANDS_50ML,
                                        cycles=pump_100ml_cycles)

            log.debug('Pco2wProtocol._handler_deionized_water_flush_execute_100ml(): SUCCESS')
            self._async_raise_fsm_event(Pco2wProtocolEvent.SUCCESS)
        except InstrumentTimeoutException:
            log.error('Pco2wProtocol._handler_deionized_water_flush_execute_100ml(): TIMEOUT')
            self._async_raise_fsm_event(Pco2wProtocolEvent.TIMEOUT)

        return None, None

    ########################################################################
    # Reagent flush 100 ml handlers.
    ########################################################################

    def _handler_reagent_flush_execute_100ml(self, *args, **kwargs):
        """
        Execute pump command, sleep to make sure it completes and make sure pump is off
        """

        try:

            pump_100ml_cycles = self._param_dict.get(Pco2wParameter.PUMP_100ML_CYCLES)
            log.debug('Pco2wProtocol._handler_reagent_flush_execute_100ml(): pump 100ml cycles = %s',
                      pump_100ml_cycles)

            flush_duration = PCO2W_PUMP_DURATION_50ML
            flush_duration_str = self._param_dict.format(Pco2wParameter.REAGENT_FLUSH_DURATION, flush_duration)
            flush_duration_seconds = flush_duration * SAMI_PUMP_DURATION_UNITS
            log.debug('Pco2wProtocol._handler_reagent_flush_execute_100ml(): flush duration param = %s, seconds = %s',
                      flush_duration,
                      flush_duration_seconds)

            # Add offset to timeout to make sure pump completes.
            flush_timeout = flush_duration_seconds + SAMI_PUMP_TIMEOUT_OFFSET

            self._execute_pump_sequence(command=Pco2wInstrumentCommand.PCO2W_PUMP_REAGENT,
                                        duration=flush_duration_str,
                                        timeout=flush_timeout,
                                        delay=PCO2W_PUMP_SLEEP_50ML,
                                        command_count=PCO2W_PUMP_COMMANDS_50ML,
                                        cycles=pump_100ml_cycles)

            log.debug('Pco2wProtocol._handler_reagent_flush_execute_100ml(): SUCCESS')
            self._async_raise_fsm_event(Pco2wProtocolEvent.SUCCESS)
        except InstrumentTimeoutException:
            log.error('Pco2wProtocol._handler_reagent_flush_execute_100ml(): TIMEOUT')
            self._async_raise_fsm_event(Pco2wProtocolEvent.TIMEOUT)

        return None, None

    ########################################################################
    # Deionized water flush handlers.
    ########################################################################

    def _handler_deionized_water_flush_execute(self, *args, **kwargs):
        """
        Execute pump command, sleep to make sure it completes and make sure pump is off
        """

        try:

            param = Pco2wParameter.DEIONIZED_WATER_FLUSH_DURATION
            flush_duration = self._param_dict.get(param)
            flush_duration_str = self._param_dict.format(param, flush_duration)
            flush_duration_seconds = flush_duration * SAMI_PUMP_DURATION_UNITS

            log.debug(
                'Pco2wProtocol._handler_deionized_water_flush_execute(): flush duration param = %s, seconds = %s',
                flush_duration,
                flush_duration_seconds)

            # Add offset to timeout make sure pump completes.
            flush_timeout = flush_duration_seconds + SAMI_PUMP_TIMEOUT_OFFSET

            self._execute_pump_sequence(command=Pco2wInstrumentCommand.PCO2W_PUMP_DEIONIZED_WATER,
                                        duration=flush_duration_str,
                                        timeout=flush_timeout,
                                        delay=0,
                                        command_count=1,
                                        cycles=1)

            log.debug('Pco2wProtocol._handler_deionized_water_flush_execute(): SUCCESS')
            self._async_raise_fsm_event(Pco2wProtocolEvent.SUCCESS)
        except InstrumentTimeoutException:
            log.error('Pco2wProtocol._handler_deionized_water_flush_execute(): TIMEOUT')
            self._async_raise_fsm_event(Pco2wProtocolEvent.TIMEOUT)

        return None, None

    ########################################################################
    # Reagent flush handlers.
    ########################################################################

    def _handler_reagent_flush_execute(self, *args, **kwargs):
        """
        Execute pump command, sleep to make sure it completes and make sure pump is off
        """

        try:
            param = SamiParameter.REAGENT_FLUSH_DURATION
            flush_duration = self._param_dict.get(param)
            flush_duration_str = self._param_dict.format(param, flush_duration)
            flush_duration_seconds = flush_duration * SAMI_PUMP_DURATION_UNITS

            log.debug('SamiProtocol._handler_reagent_flush_execute(): flush duration param = %s, seconds = %s',
                      flush_duration,
                      flush_duration_seconds)

            # Add offset to timeout to make sure pump completes.
            flush_timeout = flush_duration_seconds + SAMI_PUMP_TIMEOUT_OFFSET

            self._execute_pump_sequence(command=Pco2wInstrumentCommand.PCO2W_PUMP_REAGENT,
                                        duration=flush_duration_str,
                                        timeout=flush_timeout,
                                        delay=0,
                                        command_count=1,
                                        cycles=1)

            log.debug('SamiProtocol._handler_reagent_flush_execute(): SUCCESS')
            self._async_raise_fsm_event(Pco2wProtocolEvent.SUCCESS)
        except InstrumentTimeoutException:
            log.error('SamiProtocol._handler_reagent_flush_execute(): TIMEOUT')
            self._async_raise_fsm_event(Pco2wProtocolEvent.TIMEOUT)

        return None, None

    ########################################################################
    # Response handlers.
    ########################################################################

    def _parse_response_blank_sample_sami(self, response, prompt):
        """
        Parse response to take blank sample instrument command
        """

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
        self._do_cmd_resp(Pco2wInstrumentCommand.PCO2W_ACQUIRE_BLANK_SAMPLE,
                          timeout=self._get_blank_sample_timeout(),
                          response_regex=self._get_sample_regex())

        sample_time = time.time() - start_time

        log.debug('Pco2wProtocol._take_blank_sample(): Blank Sample took %s to FINISH', sample_time)

    ########################################################################
    # Build Command, Driver and Parameter dictionaries
    ########################################################################

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """

        SamiProtocol._build_command_dict(self)

        self._cmd_dict.add(Pco2wCapability.ACQUIRE_BLANK_SAMPLE, display_name="Acquire Blank Sample")
        self._cmd_dict.add(Pco2wCapability.DEIONIZED_WATER_FLUSH_100ML, display_name="Deionized Water Flush 100 ml")
        self._cmd_dict.add(Pco2wCapability.REAGENT_FLUSH_100ML, display_name="Reagent Flush 100 ml")
        self._cmd_dict.add(Pco2wCapability.DEIONIZED_WATER_FLUSH, display_name="Deionized Water Flush")

    def _build_param_dict(self):
        """
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """

        SamiProtocol._build_param_dict(self)

        configuration_string_regex = self._get_configuration_string_regex()

        # PCO2 0x04, PHSEN 0x0A
        self._param_dict.add(Pco2wParameter.SAMI_DRIVER_VERSION, configuration_string_regex,
                             lambda match: int(match.group(6), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x04,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Sami Driver Version')

        self._param_dict.add(Pco2wParameter.PUMP_PULSE, configuration_string_regex,
                             lambda match: int(match.group(21), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x10,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Pump Pulse Duration')

        self._param_dict.add(Pco2wParameter.PUMP_DURATION, configuration_string_regex,
                             lambda match: int(match.group(22), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x20,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Pump Measurement Duration')

        self._param_dict.add(Pco2wParameter.SAMPLES_PER_MEASUREMENT, configuration_string_regex,
                             lambda match: int(match.group(23), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0xFF,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Samples Per Measurement')

        self._param_dict.add(Pco2wParameter.CYCLES_BETWEEN_BLANKS, configuration_string_regex,
                             lambda match: int(match.group(24), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x54,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Cycles Between Blanks')

        self._param_dict.add(Pco2wParameter.NUMBER_REAGENT_CYCLES, configuration_string_regex,
                             lambda match: int(match.group(25), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x18,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Number of Reagent Cycles')

        self._param_dict.add(Pco2wParameter.NUMBER_BLANK_CYCLES, configuration_string_regex,
                             lambda match: int(match.group(26), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x1C,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Number of Blank Cycles')

        self._param_dict.add(Pco2wParameter.FLUSH_PUMP_INTERVAL, configuration_string_regex,
                             lambda match: int(match.group(27), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x01,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Flush Pump Interval')

        self._param_dict.add(Pco2wParameter.BIT_SWITCHES, configuration_string_regex,
                             lambda match: int(match.group(28), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Bit Switches')

        self._param_dict.add(Pco2wParameter.NUMBER_EXTRA_PUMP_CYCLES, configuration_string_regex,
                             lambda match: int(match.group(29), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x38,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Number of Extra Pump Cycles')

        self._param_dict.add(Pco2wParameter.PUMP_100ML_CYCLES, r'Pump 100ml cycles = ([0-9]+)',
                             lambda match: match.group(1),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=False,
                             default_value=0x1,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Pump 100ml Cycles')

        self._param_dict.add(Pco2wParameter.REAGENT_FLUSH_DURATION, r'Reagent flush duration = ([0-9]+)',
                             lambda match: match.group(1),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=False,
                             default_value=0x8,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Reagent Flush Duration')

        self._param_dict.add(Pco2wParameter.DEIONIZED_WATER_FLUSH_DURATION,
                             r'Deionized water flush duration = ([0-9]+)',
                             lambda match: match.group(1),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=False,
                             default_value=0x8,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Deionized Water Flush Duration')

    ########################################################################
    # Overridden base class methods
    ########################################################################

    def _get_blank_sample_timeout(self):
        """
        Get blank sample timeout.
        @retval blank sample timeout in seconds.
        """
        return PCO2W_SAMPLE_TIMEOUT

    def _get_sample_timeout(self):
        """
        Get sample timeout.
        @retval sample timeout in seconds.
        """
        return PCO2W_SAMPLE_TIMEOUT

    def _get_sample_regex(self):
        """
        Get sample regex
        @retval sample regex
        """
        return PCO2W_SAMPLE_REGEX_MATCHER
