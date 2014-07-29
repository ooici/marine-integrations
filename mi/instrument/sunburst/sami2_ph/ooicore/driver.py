"""
@package mi.instrument.sunburst.sami2_ph.ooicore.driver
@file marine-integrations/mi/instrument/sunburst/sami2_ph/ooicore/driver.py
@author Stuart Pearce
@brief Driver for the ooicore
Release notes:
    Sunburst Sensors SAMI2-PH pH underwater sensor.
    Derived from initial code developed by Chris Center.

    Much of this code inherits from a SAMI Base Driver at:
    marine-integrations/mi/instrument/sunburst/driver.py,
    since the SAMI2-PH & SAMI2-PCO2 instruments have the same basic
    SAMI2 operating structure.
"""

__author__ = 'Stuart Pearce & Kevin Stiemke'
__license__ = 'Apache 2.0'

import re
import time

from mi.core.log import get_logger


log = get_logger()

from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentTimeoutException

from mi.core.common import BaseEnum
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.instrument.sunburst.driver import Prompt, SamiBatteryVoltageDataParticle, SamiThermistorVoltageDataParticle
from mi.instrument.sunburst.driver import SamiDataParticleType
from mi.instrument.sunburst.driver import SamiParameter
from mi.instrument.sunburst.driver import SamiInstrumentCommand
from mi.instrument.sunburst.driver import SamiRegularStatusDataParticle
from mi.instrument.sunburst.driver import SamiControlRecordDataParticle
from mi.instrument.sunburst.driver import SamiConfigDataParticleKey
from mi.instrument.sunburst.driver import SamiInstrumentDriver
from mi.instrument.sunburst.driver import SamiProtocol

from mi.instrument.sunburst.driver import SAMI_CONTROL_RECORD_REGEX_MATCHER
from mi.instrument.sunburst.driver import SAMI_ERROR_REGEX_MATCHER
from mi.instrument.sunburst.driver import SAMI_REGULAR_STATUS_REGEX_MATCHER

from mi.instrument.sunburst.driver import SAMI_NEWLINE
from mi.instrument.sunburst.driver import SamiScheduledJob
from mi.instrument.sunburst.driver import SamiProtocolState
from mi.instrument.sunburst.driver import SamiProtocolEvent
from mi.instrument.sunburst.driver import SamiCapability
from mi.instrument.sunburst.driver import SAMI_PUMP_TIMEOUT_OFFSET
from mi.instrument.sunburst.driver import SAMI_NEW_LINE_REGEX_MATCHER
from mi.instrument.sunburst.driver import SAMI_DEFAULT_TIMEOUT
from mi.instrument.sunburst.driver import SAMI_PUMP_DURATION_UNITS

###
#    Driver Constant Definitions
###

# PHSEN sample timeout
PHSEN_SAMPLE_TIMEOUT = 240

# Pump on, valve on
PHSEN_PUMP_REAGENT_PARAM = '03'
# Pump off, value on
PHSEN_PUMP_50ML_STAGE2_PARAM = '02'  # Stage 1 is pump reagent param
# Pump on, valve off
PHSEN_PUMP_SEAWATER_PARAM = '01'
# Sleep time between seawater pumps for 2750ML
PHSEN_PUMP_SLEEP_SEAWATER_2750ML = 2.0
# Number of times to pump seawater for 2750ML
PHSEN_PUMP_COMMANDS_SEAWATER_2750ML = 55
# Duration parameter to pump seawater command for 2750ML
PHSEN_PUMP_DURATION_SEAWATER_2750ML = 2
# Sleep time after pumping 50ML of reagent
PHSEN_PUMP_SLEEP_REAGENT_50ML = 1.0
# Duration parameter to pump 50ML of reagent
PHSEN_PUMP_DURATION_REAGENT_50ML = 4

###
#    Driver RegEx Definitions
###

# PHSEN Sample Records (Type 0x0A)
PHSEN_SAMPLE_REGEX = (
    r'[\*]' +  # record identifier
    '([0-9A-Fa-f]{2})' +  # unique instrument identifier
    '([0-9A-Fa-f]{2})' +  # length of data record (bytes)
    '(0A|0B)' +  # type of data record (0A for pH)
    '([0-9A-Fa-f]{8})' +  # timestamp (seconds since 1904)
    '([0-9A-Fa-f]{4})' +  # starting thermistor reading
    '([0-9A-Fa-f]{64})' +  # 16 reference measurements
    '([0-9A-Fa-f]{368})' +  # 23 sets of 4 sample measurements
    '([0-9A-Fa-f]{4})' +  # currently unused but reserved
    '([0-9A-Fa-f]{4})' +  # battery voltage
    '([0-9A-Fa-f]{4})' +  # ending thermistor reading
    '([0-9A-Fa-f]{2})' +  # checksum
    SAMI_NEWLINE)
PHSEN_SAMPLE_REGEX_MATCHER = re.compile(PHSEN_SAMPLE_REGEX)

# Configuration Records
PHSEN_CONFIGURATION_REGEX = (
    r'([0-9A-Fa-f]{8})' +  # Launch time timestamp (seconds since 1904)
    '([0-9A-Fa-f]{8})' +  # start time (seconds from launch time)
    '([0-9A-Fa-f]{8})' +  # stop time (seconds from start time)
    '([0-9A-Fa-f]{2})' +  # mode bit field
    '([0-9A-Fa-f]{6})' +  # Sami sampling interval (seconds)
    '([0-9A-Fa-f]{2})' +  # Sami driver type (0A)
    '([0-9A-Fa-f]{2})' +  # Pointer to Sami ph config parameters
    '([0-9A-Fa-f]{6})' +  # Device 1 interval
    '([0-9A-Fa-f]{2})' +  # Device 1 driver type
    '([0-9A-Fa-f]{2})' +  # Device 1 pointer to config params
    '([0-9A-Fa-f]{6})' +  # Device 2 interval
    '([0-9A-Fa-f]{2})' +  # Device 2 driver type
    '([0-9A-Fa-f]{2})' +  # Device 2 pointer to config params
    '([0-9A-Fa-f]{6})' +  # Device 3 interval
    '([0-9A-Fa-f]{2})' +  # Device 3 driver type
    '([0-9A-Fa-f]{2})' +  # Device 3 pointer to config params
    '([0-9A-Fa-f]{6})' +  # Prestart interval
    '([0-9A-Fa-f]{2})' +  # Prestart driver type
    '([0-9A-Fa-f]{2})' +  # Prestart pointer to config params
    '([0-9A-Fa-f]{2})' +  # Global config bit field
    '([0-9A-Fa-f]{2})' +  # pH1: Number of samples averaged
    '([0-9A-Fa-f]{2})' +  # pH2: Number of Flushes
    '([0-9A-Fa-f]{2})' +  # pH3: Pump On-Flush
    '([0-9A-Fa-f]{2})' +  # pH4: Pump Off-Flush
    '([0-9A-Fa-f]{2})' +  # pH5: Number of reagent pumps
    '([0-9A-Fa-f]{2})' +  # pH6: Valve Delay
    '([0-9A-Fa-f]{2})' +  # pH7: Pump On-Ind
    '([0-9A-Fa-f]{2})' +  # pH8: Pump Off-Ind
    '([0-9A-Fa-f]{2})' +  # pH9: Number of blanks
    '([0-9A-Fa-f]{2})' +  # pH10: Pump measure T
    '([0-9A-Fa-f]{2})' +  # pH11: Pump off to measure
    '([0-9A-Fa-f]{2})' +  # pH12: Measure to pump on
    '([0-9A-Fa-f]{2})' +  # pH13: Number of measurements
    '([0-9A-Fa-f]{2})' +  # pH14: Salinity delay
    '([0-9A-Fa-f]{406})' +  # padding of F or 0
    SAMI_NEWLINE)
PHSEN_CONFIGURATION_REGEX_MATCHER = re.compile(PHSEN_CONFIGURATION_REGEX)

###
#    Begin Classes
###


class ScheduledJob(SamiScheduledJob):
    """
    Extend base class with instrument specific functionality.
    """


class ProtocolState(SamiProtocolState):
    """
    Extend base class with instrument specific functionality.
    """
    SEAWATER_FLUSH_2750ML = 'PROTOCOL_STATE_SEAWATER_FLUSH_2750ML'
    REAGENT_FLUSH_50ML = 'PROTOCOL_STATE_REAGENT_FLUSH_50ML'
    SEAWATER_FLUSH = 'PROTOCOL_STATE_SEAWATER_FLUSH'


class ProtocolEvent(SamiProtocolEvent):
    """
    Extend base class with instrument specific functionality.
    """
    SEAWATER_FLUSH_2750ML = 'DRIVER_EVENT_SEAWATER_FLUSH_2750ML'
    REAGENT_FLUSH_50ML = 'DRIVER_EVENT_REAGENT_FLUSH_50ML'
    SEAWATER_FLUSH = 'DRIVER_EVENT_SEAWATER_FLUSH'


class Capability(SamiCapability):
    """
    Extend base class with instrument specific functionality.
    """
    SEAWATER_FLUSH_2750ML = ProtocolEvent.SEAWATER_FLUSH_2750ML
    REAGENT_FLUSH_50ML = ProtocolEvent.REAGENT_FLUSH_50ML
    SEAWATER_FLUSH = ProtocolEvent.SEAWATER_FLUSH


class DataParticleType(SamiDataParticleType):
    """
    Data particle types produced by this driver
    """
    PHSEN_CONFIGURATION = 'phsen_configuration'
    PHSEN_DATA_RECORD = 'phsen_data_record'
    PHSEN_REGULAR_STATUS = 'phsen_regular_status'
    PHSEN_CONTROL_RECORD = 'phsen_control_record'
    PHSEN_BATTERY_VOLTAGE = 'phsen_battery_voltage'
    PHSEN_THERMISTOR_VOLTAGE = 'phsen_thermistor_voltage'


class Parameter(SamiParameter):
    """
    Device specific parameters.
    """
    # PHSEN driver extends the base class (SamiParameter)
    NUMBER_SAMPLES_AVERAGED = 'number_samples_averaged'
    NUMBER_FLUSHES = 'number_flushes'
    PUMP_ON_FLUSH = 'pump_on_flush'
    PUMP_OFF_FLUSH = 'pump_off_flush'
    NUMBER_REAGENT_PUMPS = 'number_reagent_pumps'
    VALVE_DELAY = 'valve_delay'
    PUMP_ON_IND = 'pump_on_ind'
    PV_OFF_IND = 'pv_off_ind'
    NUMBER_BLANKS = 'number_blanks'
    PUMP_MEASURE_T = 'pump_measure_t'
    PUMP_OFF_TO_MEASURE = 'pump_off_to_measure'
    MEASURE_TO_PUMP_ON = 'measure_to_pump_on'
    NUMBER_MEASUREMENTS = 'number_measurements'
    SALINITY_DELAY = 'salinity_delay'
    FLUSH_CYCLES = 'flush_cycles'
    SEAWATER_FLUSH_DURATION = 'seawater_flush_duration'


class InstrumentCommand(SamiInstrumentCommand):
    """
    Device specific Instrument command strings. Extends superclass
    SamiInstrumentCommand
    """
    PHSEN_PUMP_SEAWATER = 'P' + PHSEN_PUMP_SEAWATER_PARAM
    PHSEN_PUMP_REAGENT = 'P' + PHSEN_PUMP_REAGENT_PARAM
    PSHEN_PUMP_50ML_STAGE2 = 'P' + PHSEN_PUMP_50ML_STAGE2_PARAM


###############################################################################
# Data Particles
###############################################################################

#Redefine the data particle type so each particle has a unique name
SamiBatteryVoltageDataParticle._data_particle_type = DataParticleType.PHSEN_BATTERY_VOLTAGE
SamiThermistorVoltageDataParticle._data_particle_type = DataParticleType.PHSEN_THERMISTOR_VOLTAGE
SamiRegularStatusDataParticle._data_particle_type = DataParticleType.PHSEN_REGULAR_STATUS
SamiControlRecordDataParticle._data_particle_type = DataParticleType.PHSEN_CONTROL_RECORD


class PhsenSamiSampleDataParticleKey(BaseEnum):
    """
    Data particle key for the SAMI2-PH records. These particles
    capture when a sample was processed.
    """
    UNIQUE_ID = 'unique_id'
    RECORD_LENGTH = 'record_length'
    RECORD_TYPE = 'record_type'
    RECORD_TIME = 'record_time'
    START_THERMISTOR = 'thermistor_start'
    REF_MEASUREMENTS = 'reference_light_measurements'
    PH_MEASUREMENTS = 'ph_light_measurements'
    RESERVED_UNUSED = 'unused'
    VOLTAGE_BATTERY = 'voltage_battery'
    END_THERMISTOR = 'thermistor_end'
    CHECKSUM = 'checksum'


class PhsenSamiSampleDataParticle(DataParticle):
    """
    Routines for parsing raw data into a SAMI2-PH sample data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """
    _data_particle_type = DataParticleType.PHSEN_DATA_RECORD

    def _build_parsed_values(self):
        """
        Parse SAMI2-PH values from raw data into a dictionary
        """

        matched = PHSEN_SAMPLE_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [PhsenSamiSampleDataParticleKey.UNIQUE_ID,
                         PhsenSamiSampleDataParticleKey.RECORD_LENGTH,
                         PhsenSamiSampleDataParticleKey.RECORD_TYPE,
                         PhsenSamiSampleDataParticleKey.RECORD_TIME,
                         PhsenSamiSampleDataParticleKey.START_THERMISTOR,
                         PhsenSamiSampleDataParticleKey.REF_MEASUREMENTS,
                         PhsenSamiSampleDataParticleKey.PH_MEASUREMENTS,
                         PhsenSamiSampleDataParticleKey.RESERVED_UNUSED,
                         PhsenSamiSampleDataParticleKey.VOLTAGE_BATTERY,
                         PhsenSamiSampleDataParticleKey.END_THERMISTOR,
                         PhsenSamiSampleDataParticleKey.CHECKSUM]

        result = []
        grp_index = 1  # regex group index counter
        unhex = lambda x: int(x, 16)

        # Create secondary regexes to read the ref set and ph set into
        # lists before putting into the data particle.

        # From the regex data sample match, group 5 is a set of 16
        # reference light measurements, and group 6 is a set of 92 light
        # measurements from which determines pH
        ref_measurements_string = matched.groups()[5]
        ph_measurements_string = matched.groups()[6]

        # 16 reference light measurements each 2 bytes (4 hex digits)
        ref_regex = r'([0-9A-Fa-f]{4})' * 16
        ref_regex_matcher = re.compile(ref_regex)
        ref_match = ref_regex_matcher.match(ref_measurements_string)
        ref_measurements = map(unhex, list(ref_match.groups()))

        # 92 ph measurements (23 sets of 4 measurement types)
        # each 2 bytes (4 hex digits)
        ph_regex = r'([0-9A-Fa-f]{4})' * 92
        ph_regex_matcher = re.compile(ph_regex)
        ph_match = ph_regex_matcher.match(ph_measurements_string)
        ph_measurements = map(unhex, list(ph_match.groups()))

        # fill out the data particle with values
        for key in particle_keys:
            if key is PhsenSamiSampleDataParticleKey.REF_MEASUREMENTS:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: ref_measurements})
            elif key is PhsenSamiSampleDataParticleKey.PH_MEASUREMENTS:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: ph_measurements})
            else:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: unhex(matched.group(grp_index))})
            grp_index += 1

        return result


class PhsenConfigDataParticleKey(SamiConfigDataParticleKey):
    """
    Data particle key for the configuration record.
    """
    # PHSEN driver extends the base class (SamiConfiDataParticleKey)
    NUMBER_SAMPLES_AVERAGED = 'number_samples_averaged'
    NUMBER_FLUSHES = 'number_flushes'
    PUMP_ON_FLUSH = 'pump_on_flush'
    PUMP_OFF_FLUSH = 'pump_off_flush'
    NUMBER_REAGENT_PUMPS = 'number_reagent_pumps'
    VALVE_DELAY = 'valve_delay'
    PUMP_ON_IND = 'pump_on_ind'
    PV_OFF_IND = 'pv_off_ind'
    NUMBER_BLANKS = 'number_blanks'
    PUMP_MEASURE_T = 'pump_measure_t'
    PUMP_OFF_TO_MEASURE = 'pump_off_to_measure'
    MEASURE_TO_PUMP_ON = 'measure_to_pump_on'
    NUMBER_MEASUREMENTS = 'number_measurements'
    SALINITY_DELAY = 'salinity_delay'


class PhsenConfigDataParticle(DataParticle):
    """
    Routines for parsing raw data into a configuration record data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """
    _data_particle_type = DataParticleType.PHSEN_CONFIGURATION

    def _build_parsed_values(self):
        """
        Parse configuration record values from raw data into a dictionary
        """

        matched = PHSEN_CONFIGURATION_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [PhsenConfigDataParticleKey.LAUNCH_TIME,
                         PhsenConfigDataParticleKey.START_TIME_OFFSET,
                         PhsenConfigDataParticleKey.RECORDING_TIME,
                         PhsenConfigDataParticleKey.PMI_SAMPLE_SCHEDULE,
                         PhsenConfigDataParticleKey.SAMI_SAMPLE_SCHEDULE,
                         PhsenConfigDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE,
                         PhsenConfigDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE,
                         PhsenConfigDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE,
                         PhsenConfigDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE,
                         PhsenConfigDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE,
                         PhsenConfigDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE,
                         PhsenConfigDataParticleKey.TIMER_INTERVAL_SAMI,
                         PhsenConfigDataParticleKey.DRIVER_ID_SAMI,
                         PhsenConfigDataParticleKey.PARAMETER_POINTER_SAMI,
                         PhsenConfigDataParticleKey.TIMER_INTERVAL_DEVICE1,
                         PhsenConfigDataParticleKey.DRIVER_ID_DEVICE1,
                         PhsenConfigDataParticleKey.PARAMETER_POINTER_DEVICE1,
                         PhsenConfigDataParticleKey.TIMER_INTERVAL_DEVICE2,
                         PhsenConfigDataParticleKey.DRIVER_ID_DEVICE2,
                         PhsenConfigDataParticleKey.PARAMETER_POINTER_DEVICE2,
                         PhsenConfigDataParticleKey.TIMER_INTERVAL_DEVICE3,
                         PhsenConfigDataParticleKey.DRIVER_ID_DEVICE3,
                         PhsenConfigDataParticleKey.PARAMETER_POINTER_DEVICE3,
                         PhsenConfigDataParticleKey.TIMER_INTERVAL_PRESTART,
                         PhsenConfigDataParticleKey.DRIVER_ID_PRESTART,
                         PhsenConfigDataParticleKey.PARAMETER_POINTER_PRESTART,
                         PhsenConfigDataParticleKey.USE_BAUD_RATE_57600,
                         PhsenConfigDataParticleKey.SEND_RECORD_TYPE,
                         PhsenConfigDataParticleKey.SEND_LIVE_RECORDS,
                         PhsenConfigDataParticleKey.EXTEND_GLOBAL_CONFIG,
                         PhsenConfigDataParticleKey.NUMBER_SAMPLES_AVERAGED,
                         PhsenConfigDataParticleKey.NUMBER_FLUSHES,
                         PhsenConfigDataParticleKey.PUMP_ON_FLUSH,
                         PhsenConfigDataParticleKey.PUMP_OFF_FLUSH,
                         PhsenConfigDataParticleKey.NUMBER_REAGENT_PUMPS,
                         PhsenConfigDataParticleKey.VALVE_DELAY,
                         PhsenConfigDataParticleKey.PUMP_ON_IND,
                         PhsenConfigDataParticleKey.PV_OFF_IND,
                         PhsenConfigDataParticleKey.NUMBER_BLANKS,
                         PhsenConfigDataParticleKey.PUMP_MEASURE_T,
                         PhsenConfigDataParticleKey.PUMP_OFF_TO_MEASURE,
                         PhsenConfigDataParticleKey.MEASURE_TO_PUMP_ON,
                         PhsenConfigDataParticleKey.NUMBER_MEASUREMENTS,
                         PhsenConfigDataParticleKey.SALINITY_DELAY]

        result = []
        grp_index = 1
        mode_index = 0
        glbl_index = 0
        #sami_index = 0

        for key in particle_keys:
            if key in [PhsenConfigDataParticleKey.PMI_SAMPLE_SCHEDULE,
                       PhsenConfigDataParticleKey.SAMI_SAMPLE_SCHEDULE,
                       PhsenConfigDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE,
                       PhsenConfigDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE,
                       PhsenConfigDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE,
                       PhsenConfigDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE,
                       PhsenConfigDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE,
                       PhsenConfigDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(4), 16) & (1 << mode_index))})
                mode_index += 1
                grp_index = 5

            elif key in [PhsenConfigDataParticleKey.USE_BAUD_RATE_57600,
                         PhsenConfigDataParticleKey.SEND_RECORD_TYPE,
                         PhsenConfigDataParticleKey.SEND_LIVE_RECORDS,
                         PhsenConfigDataParticleKey.EXTEND_GLOBAL_CONFIG]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(20), 16) & (1 << glbl_index))})
                glbl_index += 1
                if glbl_index == 3:
                    glbl_index = 7
                grp_index = 21

            else:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
                grp_index += 1

        return result


###############################################################################
# Driver
###############################################################################


class InstrumentDriver(SamiInstrumentDriver):
    """
    InstrumentDriver subclass Subclasses SamiInstrumentDriver and
    SingleConnectionInstrumentDriver with connection state machine.
    """

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
        self._protocol = Protocol(Prompt, SAMI_NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################


class Protocol(SamiProtocol):
    """
    Instrument protocol class
    Subclasses SamiProtocol and CommandResponseInstrumentProtocol
    """

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """

        # Build protocol state machine.
        self._protocol_fsm = ThreadSafeFSM(
            ProtocolState, ProtocolEvent,
            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Construct protocol superclass.
        SamiProtocol.__init__(self, prompts, newline, driver_event)

        self._protocol_fsm.add_handler(
            ProtocolState.COMMAND, ProtocolEvent.SEAWATER_FLUSH_2750ML,
            self._handler_command_seawater_flush_2750ml)
        self._protocol_fsm.add_handler(
            ProtocolState.COMMAND, ProtocolEvent.REAGENT_FLUSH_50ML,
            self._handler_command_reagent_flush_50ml)
        self._protocol_fsm.add_handler(
            ProtocolState.COMMAND, ProtocolEvent.SEAWATER_FLUSH,
            self._handler_command_seawater_flush)

        # this state would be entered whenever a SEAWATER_FLUSH_2750ML event
        # occurred while in the COMMAND state
        self._protocol_fsm.add_handler(
            ProtocolState.SEAWATER_FLUSH_2750ML, ProtocolEvent.ENTER,
            self._execution_state_enter)
        self._protocol_fsm.add_handler(
            ProtocolState.SEAWATER_FLUSH_2750ML, ProtocolEvent.EXIT,
            self._execution_state_exit)
        self._protocol_fsm.add_handler(
            ProtocolState.SEAWATER_FLUSH_2750ML, ProtocolEvent.EXECUTE,
            self._handler_seawater_flush_execute_2750ml)
        self._protocol_fsm.add_handler(
            ProtocolState.SEAWATER_FLUSH_2750ML, ProtocolEvent.SUCCESS,
            self._execution_success_to_command_state)
        self._protocol_fsm.add_handler(
            ProtocolState.SEAWATER_FLUSH_2750ML, ProtocolEvent.TIMEOUT,
            self._execution_timeout_to_command_state)
        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            ProtocolState.SEAWATER_FLUSH_2750ML, ProtocolEvent.ACQUIRE_STATUS,
            self._handler_queue_acquire_status)

        # this state would be entered whenever a PUMP_REAGENT_50ML event
        # occurred while in the COMMAND state
        self._protocol_fsm.add_handler(
            ProtocolState.REAGENT_FLUSH_50ML, ProtocolEvent.ENTER,
            self._execution_state_enter)
        self._protocol_fsm.add_handler(
            ProtocolState.REAGENT_FLUSH_50ML, ProtocolEvent.EXIT,
            self._execution_state_exit)
        self._protocol_fsm.add_handler(
            ProtocolState.REAGENT_FLUSH_50ML, ProtocolEvent.EXECUTE,
            self._handler_reagent_flush_execute_50ml)
        self._protocol_fsm.add_handler(
            ProtocolState.REAGENT_FLUSH_50ML, ProtocolEvent.SUCCESS,
            self._execution_success_to_command_state)
        self._protocol_fsm.add_handler(
            ProtocolState.REAGENT_FLUSH_50ML, ProtocolEvent.TIMEOUT,
            self._execution_timeout_to_command_state)
        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            ProtocolState.REAGENT_FLUSH_50ML, ProtocolEvent.ACQUIRE_STATUS,
            self._handler_queue_acquire_status)

        # this state would be entered whenever a SEAWATER_FLUSH event
        # occurred while in the COMMAND state
        self._protocol_fsm.add_handler(
            ProtocolState.SEAWATER_FLUSH, ProtocolEvent.ENTER,
            self._execution_state_enter)
        self._protocol_fsm.add_handler(
            ProtocolState.SEAWATER_FLUSH, ProtocolEvent.EXIT,
            self._execution_state_exit)
        self._protocol_fsm.add_handler(
            ProtocolState.SEAWATER_FLUSH, ProtocolEvent.EXECUTE,
            self._handler_seawater_flush_execute)
        self._protocol_fsm.add_handler(
            ProtocolState.SEAWATER_FLUSH, ProtocolEvent.SUCCESS,
            self._execution_success_to_command_state)
        self._protocol_fsm.add_handler(
            ProtocolState.SEAWATER_FLUSH, ProtocolEvent.TIMEOUT,
            self._execution_timeout_to_command_state)
        ## Events to queue - intended for schedulable events occurring when a sample is being taken
        self._protocol_fsm.add_handler(
            ProtocolState.SEAWATER_FLUSH, ProtocolEvent.ACQUIRE_STATUS,
            self._handler_queue_acquire_status)

        self._engineering_parameters.append(Parameter.FLUSH_CYCLES)
        self._engineering_parameters.append(Parameter.SEAWATER_FLUSH_DURATION)

        self._add_build_handler(InstrumentCommand.PHSEN_PUMP_REAGENT, self._build_pump_command)
        self._add_build_handler(InstrumentCommand.PHSEN_PUMP_SEAWATER, self._build_pump_command)
        self._add_build_handler(InstrumentCommand.PSHEN_PUMP_50ML_STAGE2, self._build_pump_command)

        self._add_response_handler(InstrumentCommand.PHSEN_PUMP_REAGENT, self._parse_response_newline)
        self._add_response_handler(InstrumentCommand.PHSEN_PUMP_SEAWATER, self._parse_response_newline)
        self._add_response_handler(InstrumentCommand.PSHEN_PUMP_50ML_STAGE2, self._parse_response_newline)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # build the chunker bot
        self._chunker = StringChunker(Protocol.sieve_function)

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_seawater_flush_2750ml(self):
        """
        Flush with seawater
        """

        next_state = ProtocolState.SEAWATER_FLUSH_2750ML
        next_agent_state = ResourceAgentState.BUSY
        result = None

        return next_state, (next_agent_state, result)

    def _handler_command_reagent_flush_50ml(self):
        """
        Flush with reagent
        """

        next_state = ProtocolState.REAGENT_FLUSH_50ML
        next_agent_state = ResourceAgentState.BUSY
        result = None

        return next_state, (next_agent_state, result)

    def _handler_command_seawater_flush(self):
        """
        Flush with seawater
        """

        next_state = ProtocolState.SEAWATER_FLUSH
        next_agent_state = ResourceAgentState.BUSY
        result = None

        return next_state, (next_agent_state, result)

    ########################################################################
    # Seawater flush 2750 ml handlers.
    ########################################################################

    def _handler_seawater_flush_execute_2750ml(self, *args, **kwargs):
        """
        Execute pump command, sleep to make sure it completes and make sure pump is off
        """

        try:

            flush_cycles = self._param_dict.get(Parameter.FLUSH_CYCLES)
            log.debug('Pco2wProtocol._handler_seawater_flush_execute_2750ml(): flush cycles = %s', flush_cycles)

            flush_duration = PHSEN_PUMP_DURATION_SEAWATER_2750ML
            flush_duration_str = self._param_dict.format(Parameter.SEAWATER_FLUSH_DURATION, flush_duration)
            flush_duration_seconds = flush_duration * SAMI_PUMP_DURATION_UNITS
            log.debug(
                'Pco2wProtocol._handler_seawater_flush_execute_2750mll(): flush duration param = %s, seconds = %s',
                flush_duration, flush_duration_seconds)

            # Add offset to timeout to make sure pump completes.
            flush_timeout = flush_duration_seconds + SAMI_PUMP_TIMEOUT_OFFSET

            self._execute_pump_sequence(command=InstrumentCommand.PHSEN_PUMP_SEAWATER,
                                        duration=flush_duration_str,
                                        timeout=flush_timeout,
                                        delay=PHSEN_PUMP_SLEEP_SEAWATER_2750ML,
                                        command_count=PHSEN_PUMP_COMMANDS_SEAWATER_2750ML,
                                        cycles=flush_cycles)

            log.debug('Protocol._handler_seawater_flush_execute_2750ml(): SUCCESS')
            self._async_raise_fsm_event(ProtocolEvent.SUCCESS)
        except InstrumentTimeoutException:
            log.error('Protocol._handler_seawater_flush_execute_2750ml(): TIMEOUT')
            self._async_raise_fsm_event(ProtocolEvent.TIMEOUT)

        return None, None

    ########################################################################
    # Reagent flush 100 ml handlers.
    ########################################################################

    def _handler_reagent_flush_execute_50ml(self, *args, **kwargs):
        """
        Execute pump command, sleep to make sure it completes and make sure pump is off
        """

        try:

            flush_cycles = self._param_dict.get(Parameter.FLUSH_CYCLES)
            log.debug('Pco2wProtocol._handler_reagent_flush_execute_50ml(): flush cycles = %s', flush_cycles)

            flush_duration = PHSEN_PUMP_DURATION_REAGENT_50ML
            flush_duration_str = self._param_dict.format(Parameter.REAGENT_FLUSH_DURATION, flush_duration)
            flush_duration_seconds = flush_duration * SAMI_PUMP_DURATION_UNITS
            log.debug('Pco2wProtocol._handler_reagent_flush_execute_50ml(): flush duration param = %s, seconds = %s',
                      flush_duration, flush_duration_seconds)

            # Add offset to timeout to make sure pump completes.
            flush_timeout = flush_duration_seconds + SAMI_PUMP_TIMEOUT_OFFSET

            self._wakeup()

            for cycle_num in xrange(flush_cycles):
                self._do_cmd_resp_no_wakeup(InstrumentCommand.PHSEN_PUMP_REAGENT,
                                            flush_duration_str,
                                            timeout=flush_timeout,
                                            response_regex=SAMI_NEW_LINE_REGEX_MATCHER)
                self._do_cmd_resp_no_wakeup(InstrumentCommand.PSHEN_PUMP_50ML_STAGE2,
                                            flush_duration_str,
                                            timeout=flush_timeout,
                                            response_regex=SAMI_NEW_LINE_REGEX_MATCHER)
                time.sleep(PHSEN_PUMP_SLEEP_REAGENT_50ML)

            # Make sure pump is off
            self._do_cmd_resp_no_wakeup(InstrumentCommand.SAMI_PUMP_OFF, timeout=SAMI_DEFAULT_TIMEOUT,
                                        response_regex=SAMI_NEW_LINE_REGEX_MATCHER)

            log.debug('Protocol._handler_reagent_flush_enter_50ml(): SUCCESS')
            self._async_raise_fsm_event(ProtocolEvent.SUCCESS)
        except InstrumentTimeoutException:
            log.error('Protocol._handler_reagent_flush_enter_50ml(): TIMEOUT')
            self._async_raise_fsm_event(ProtocolEvent.TIMEOUT)

        return None, None

    ########################################################################
    # Seawater flush ml handlers.
    ########################################################################

    def _handler_seawater_flush_execute(self, *args, **kwargs):
        """
        Execute pump command, sleep to make sure it completes and make sure pump is off
        """

        try:

            param = Parameter.SEAWATER_FLUSH_DURATION
            flush_duration = self._param_dict.get(param)
            flush_duration_str = self._param_dict.format(param, flush_duration)
            flush_duration_seconds = flush_duration * SAMI_PUMP_DURATION_UNITS

            log.debug('Protocol._handler_seawater_flush_execute(): flush duration param = %s, seconds = %s',
                      flush_duration, flush_duration_seconds)

            # Add offset to timeout to make sure pump completes.
            flush_timeout = flush_duration_seconds + SAMI_PUMP_TIMEOUT_OFFSET

            self._execute_pump_sequence(command=InstrumentCommand.PHSEN_PUMP_SEAWATER,
                                        duration=flush_duration_str,
                                        timeout=flush_timeout,
                                        delay=0,
                                        command_count=1,
                                        cycles=1)

            log.debug('Protocol._handler_seawater_flush_execute(): SUCCESS')
            self._async_raise_fsm_event(ProtocolEvent.SUCCESS)
        except InstrumentTimeoutException:
            log.error('Protocol._handler_seawater_flush_execute(): TIMEOUT')
            self._async_raise_fsm_event(ProtocolEvent.TIMEOUT)

        return None, None

    ########################################################################
    # Reagent flush handlers.
    ########################################################################

    def _handler_reagent_flush_execute(self, *args, **kwargs):
        """
        Execute pump command, sleep to make sure it completes and make sure pump is off
        """

        try:

            param = Parameter.REAGENT_FLUSH_DURATION
            flush_duration = self._param_dict.get(param)
            flush_duration_str = self._param_dict.format(param, flush_duration)
            flush_duration_seconds = flush_duration * SAMI_PUMP_DURATION_UNITS

            log.debug('Protocol._handler_reagent_flush_execute(): flush duration param = %s, seconds = %s',
                      flush_duration, flush_duration_seconds)

            # Add offset to timeout to make sure pump completes.
            flush_timeout = flush_duration_seconds + SAMI_PUMP_TIMEOUT_OFFSET

            self._execute_pump_sequence(command=InstrumentCommand.PHSEN_PUMP_REAGENT,
                                        duration=flush_duration_str,
                                        timeout=flush_timeout,
                                        delay=0,
                                        command_count=1,
                                        cycles=1)

            log.debug('SamiProtocol._handler_reagent_flush_execute(): SUCCESS')
            self._async_raise_fsm_event(SamiProtocolEvent.SUCCESS)
        except InstrumentTimeoutException:
            log.error('SamiProtocol._handler_reagent_flush_execute(): TIMEOUT')
            self._async_raise_fsm_event(SamiProtocolEvent.TIMEOUT)

        return None, None

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """

        return [x for x in events if Capability.has(x)]

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        :param raw_data: data to filter
        """

        return_list = []

        sieve_matchers = [SAMI_REGULAR_STATUS_REGEX_MATCHER,
                          SAMI_CONTROL_RECORD_REGEX_MATCHER,
                          PHSEN_SAMPLE_REGEX_MATCHER,
                          PHSEN_CONFIGURATION_REGEX_MATCHER,
                          SAMI_ERROR_REGEX_MATCHER]

        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """

        if any([self._extract_sample(SamiRegularStatusDataParticle, SAMI_REGULAR_STATUS_REGEX_MATCHER,
                                     chunk, timestamp),
                self._extract_sample(SamiControlRecordDataParticle, SAMI_CONTROL_RECORD_REGEX_MATCHER,
                                     chunk, timestamp),
                self._extract_sample(PhsenConfigDataParticle, PHSEN_CONFIGURATION_REGEX_MATCHER,
                                     chunk, timestamp)]):
            return

        sample = self._extract_sample(PhsenSamiSampleDataParticle, PHSEN_SAMPLE_REGEX_MATCHER, chunk, timestamp)

        log.debug('Protocol._got_chunk(): get_current_state() == %s', self.get_current_state())

        if sample:
            self._verify_checksum(chunk, PHSEN_SAMPLE_REGEX_MATCHER)

    ########################################################################
    # Build Command
    ########################################################################

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """

        SamiProtocol._build_command_dict(self)
        self._cmd_dict.add(Capability.SEAWATER_FLUSH_2750ML, display_name="Seawater Flush 2750 ml")
        self._cmd_dict.add(Capability.REAGENT_FLUSH_50ML, display_name="Reagent Flush 50 ml")
        self._cmd_dict.add(Capability.SEAWATER_FLUSH, display_name="Seawater Flush")

        ####################################################################
        # Build Parameter dictionary
        ####################################################################

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        SamiProtocol._build_param_dict(self)

        configuration_string_regex = self._get_configuration_string_regex()

        # Changed from 0x0A to 0x02 to indicate there is no external device
        self._param_dict.add(Parameter.MODE_BITS, configuration_string_regex,
                             lambda match: int(match.group(4), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x02,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Mode Bits')

        # PCO2 0x04, PHSEN 0x0A
        self._param_dict.add(Parameter.SAMI_DRIVER_VERSION, configuration_string_regex,
                             lambda match: int(match.group(6), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x0A,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Sami Driver Version')

        self._param_dict.add(Parameter.DEVICE1_SAMPLE_INTERVAL, configuration_string_regex,
                             lambda match: int(match.group(8), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x000000,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Device 1 Sample Interval')

        self._param_dict.add(Parameter.DEVICE1_DRIVER_VERSION, configuration_string_regex,
                             lambda match: int(match.group(9), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Device 1 Driver Version')

        self._param_dict.add(Parameter.DEVICE1_PARAMS_POINTER, configuration_string_regex,
                             lambda match: int(match.group(10), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='Device 1 Parameter Pointer')

        self._param_dict.add(Parameter.NUMBER_SAMPLES_AVERAGED, configuration_string_regex,
                             lambda match: int(match.group(21), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x01,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Number of Samples Averaged')

        self._param_dict.add(Parameter.NUMBER_FLUSHES, configuration_string_regex,
                             lambda match: int(match.group(22), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x37,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Number of Flushes')

        self._param_dict.add(Parameter.PUMP_ON_FLUSH, configuration_string_regex,
                             lambda match: int(match.group(23), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x04,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Pump On Flush')

        self._param_dict.add(Parameter.PUMP_OFF_FLUSH, configuration_string_regex,
                             lambda match: int(match.group(24), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x20,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Pump Off Flush')

        self._param_dict.add(Parameter.NUMBER_REAGENT_PUMPS, configuration_string_regex,
                             lambda match: int(match.group(25), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x01,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Number of Reagent Pumps')

        self._param_dict.add(Parameter.VALVE_DELAY, configuration_string_regex,
                             lambda match: int(match.group(26), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x08,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Valve Delay')

        self._param_dict.add(Parameter.PUMP_ON_IND, configuration_string_regex,
                             lambda match: int(match.group(27), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x08,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Pump On Ind')

        self._param_dict.add(Parameter.PV_OFF_IND, configuration_string_regex,
                             lambda match: int(match.group(28), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x10,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='P/V Off Ind')

        self._param_dict.add(Parameter.NUMBER_BLANKS, configuration_string_regex,
                             lambda match: int(match.group(29), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x04,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Number of Blanks')

        self._param_dict.add(Parameter.PUMP_MEASURE_T, configuration_string_regex,
                             lambda match: int(match.group(30), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x08,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Pump Measure T')

        self._param_dict.add(Parameter.PUMP_OFF_TO_MEASURE, configuration_string_regex,
                             lambda match: int(match.group(31), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x10,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Pump Off to Measure')

        self._param_dict.add(Parameter.MEASURE_TO_PUMP_ON, configuration_string_regex,
                             lambda match: int(match.group(32), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x08,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Measure to Pump On')

        self._param_dict.add(Parameter.NUMBER_MEASUREMENTS, configuration_string_regex,
                             lambda match: int(match.group(33), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x17,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Number of Measurements')

        self._param_dict.add(Parameter.SALINITY_DELAY, configuration_string_regex,
                             lambda match: int(match.group(34), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Salinity Delay')

        self._param_dict.add(Parameter.FLUSH_CYCLES, r'flush cycles = ([0-9]+)',
                             lambda match: match.group(1),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=False,
                             default_value=0x1,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Seawater 2750ml and Reagent 50ml Flush Cycles')

        self._param_dict.add(Parameter.REAGENT_FLUSH_DURATION, r'Reagent flush duration = ([0-9]+)',
                             lambda match: match.group(1),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=False,
                             default_value=0x4,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Flush Duration')

        self._param_dict.add(Parameter.SEAWATER_FLUSH_DURATION, r'Seawater flush duration = ([0-9]+)',
                             lambda match: match.group(1),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=False,
                             default_value=0x2,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='Flush Duration')

    def _get_specific_configuration_string_parameters(self):

        # An ordered list of parameters, can not use unordered dict
        # PCO2W driver extends the base class (SamiParameter)
        parameter_list = [Parameter.START_TIME_FROM_LAUNCH,
                          Parameter.STOP_TIME_FROM_START,
                          Parameter.MODE_BITS,
                          Parameter.SAMI_SAMPLE_INTERVAL,
                          Parameter.SAMI_DRIVER_VERSION,
                          Parameter.SAMI_PARAMS_POINTER,
                          Parameter.DEVICE1_SAMPLE_INTERVAL,
                          Parameter.DEVICE1_DRIVER_VERSION,
                          Parameter.DEVICE1_PARAMS_POINTER,
                          Parameter.DEVICE2_SAMPLE_INTERVAL,
                          Parameter.DEVICE2_DRIVER_VERSION,
                          Parameter.DEVICE2_PARAMS_POINTER,
                          Parameter.DEVICE3_SAMPLE_INTERVAL,
                          Parameter.DEVICE3_DRIVER_VERSION,
                          Parameter.DEVICE3_PARAMS_POINTER,
                          Parameter.PRESTART_SAMPLE_INTERVAL,
                          Parameter.PRESTART_DRIVER_VERSION,
                          Parameter.PRESTART_PARAMS_POINTER,
                          Parameter.GLOBAL_CONFIGURATION,
                          Parameter.NUMBER_SAMPLES_AVERAGED,
                          Parameter.NUMBER_FLUSHES,
                          Parameter.PUMP_ON_FLUSH,
                          Parameter.PUMP_OFF_FLUSH,
                          Parameter.NUMBER_REAGENT_PUMPS,
                          Parameter.VALVE_DELAY,
                          Parameter.PUMP_ON_IND,
                          Parameter.PV_OFF_IND,
                          Parameter.NUMBER_BLANKS,
                          Parameter.PUMP_MEASURE_T,
                          Parameter.PUMP_OFF_TO_MEASURE,
                          Parameter.MEASURE_TO_PUMP_ON,
                          Parameter.NUMBER_MEASUREMENTS,
                          Parameter.SALINITY_DELAY]

        return parameter_list

    def _get_configuration_string_regex(self):
        """
        Get configuration string regex.
        @retval configuration string regex.
        """
        return PHSEN_CONFIGURATION_REGEX

    def _get_configuration_string_regex_matcher(self):
        """
        Get config string regex matcher.
        @retval configuration string regex matcher
        """
        return PHSEN_CONFIGURATION_REGEX_MATCHER

    def _get_sample_timeout(self):
        """
        Get sample timeout.
        @retval sample timeout in seconds.
        """
        return PHSEN_SAMPLE_TIMEOUT

    def _get_sample_regex(self):
        """
        Get sample regex
        @retval sample regex
        """
        return PHSEN_SAMPLE_REGEX_MATCHER

# End of File driver.py
