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

from mi.core.log import get_logger

log = get_logger()

from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentProtocolException
#from mi.core.exceptions import InstrumentParameterException

from mi.core.common import BaseEnum
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.instrument.sunburst.driver import Prompt
from mi.instrument.sunburst.driver import SamiDataParticleType
from mi.instrument.sunburst.driver import SamiParameter
from mi.instrument.sunburst.driver import SamiInstrumentCommand
from mi.instrument.sunburst.driver import SamiRegularStatusDataParticle
from mi.instrument.sunburst.driver import SamiControlRecordDataParticle
from mi.instrument.sunburst.driver import SamiConfigDataParticleKey
from mi.instrument.sunburst.driver import SamiInstrumentDriver
from mi.instrument.sunburst.driver import SamiProtocol
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol

from mi.instrument.sunburst.driver import CONTROL_RECORD_REGEX_MATCHER
from mi.instrument.sunburst.driver import ERROR_REGEX_MATCHER
from mi.instrument.sunburst.driver import REGULAR_STATUS_REGEX_MATCHER

from mi.instrument.sunburst.driver import NEWLINE
from mi.instrument.sunburst.driver import TIMEOUT
from mi.instrument.sunburst.driver import SamiScheduledJob
from mi.instrument.sunburst.driver import SamiProtocolState
from mi.instrument.sunburst.driver import SamiProtocolEvent
from mi.instrument.sunburst.driver import SamiCapability

###
#    Driver Constant Definitions
###

SAMPLE_DELAY = 240

###
#    Driver RegEx Definitions
###

# SAMI pH Sample Records (Type 0x0A)
SAMI_SAMPLE_REGEX = (
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
    NEWLINE)
SAMI_SAMPLE_REGEX_MATCHER = re.compile(SAMI_SAMPLE_REGEX)

# Configuration Records
CONFIGURATION_REGEX = (
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
    NEWLINE)
CONFIGURATION_REGEX_MATCHER = re.compile(CONFIGURATION_REGEX)

###
#    Begin Classes
###

class ScheduledJob(SamiScheduledJob):
    """
    Extend base class with instrument specific functionality.
    """
    pass

class ProtocolState(SamiProtocolState):
    """
    Extend base class with instrument specific functionality.
    """
    pass

class ProtocolEvent(SamiProtocolEvent):
    """
    Extend base class with instrument specific functionality.
    """
    pass

class Capability(SamiCapability):
    """
    Extend base class with instrument specific functionality.
    """
    pass

class DataParticleType(SamiDataParticleType):
    """
    Data particle types produced by this driver
    """
    CONFIGURATION = 'phsen_configuration'
    SAMI_SAMPLE = 'phsen_sami_data_record'


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

class InstrumentCommand(SamiInstrumentCommand):
    """
    Device specific Instrument command strings. Extends superclass
    SamiInstrumentCommand
    """
    pass


###############################################################################
# Data Particles
###############################################################################


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
    _data_particle_type = DataParticleType.SAMI_SAMPLE

    def _build_parsed_values(self):
        """
        Parse SAMI2-PH values from raw data into a dictionary
        """

        matched = SAMI_SAMPLE_REGEX_MATCHER.match(self.raw_data)
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
    _data_particle_type = DataParticleType.CONFIGURATION

    def _build_parsed_values(self):
        """
        Parse configuration record values from raw data into a dictionary
        """

        matched = CONFIGURATION_REGEX_MATCHER.match(self.raw_data)
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
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


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

        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = InstrumentFSM(
            ProtocolState, ProtocolEvent,
            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Construct protocol superclass.
        SamiProtocol.__init__(self, prompts, newline, driver_event)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # build the chunker bot
        self._chunker = StringChunker(Protocol.sieve_function)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """

        return [x for x in events if Capability.has(x)]

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """

        return_list = []

        sieve_matchers = [REGULAR_STATUS_REGEX_MATCHER,
                          CONTROL_RECORD_REGEX_MATCHER,
                          SAMI_SAMPLE_REGEX_MATCHER,
                          CONFIGURATION_REGEX_MATCHER,
                          ERROR_REGEX_MATCHER]

        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """

        self._extract_sample(SamiRegularStatusDataParticle, REGULAR_STATUS_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(SamiControlRecordDataParticle, CONTROL_RECORD_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(PhsenConfigDataParticle, CONFIGURATION_REGEX_MATCHER, chunk, timestamp)
        sample = self._extract_sample(PhsenSamiSampleDataParticle, SAMI_SAMPLE_REGEX_MATCHER, chunk, timestamp)

        log.debug('herb: ' + 'Protocol._got_chunk(): get_current_state() == ' + self.get_current_state())

        if sample:
            self._verify_checksum(chunk, SAMI_SAMPLE_REGEX_MATCHER)

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
                             display_name='mode bits (set to 00000010)')

        # PCO2 0x04, PHSEN 0x0A
        self._param_dict.add(Parameter.SAMI_DRIVER_VERSION, configuration_string_regex,
                             lambda match: int(match.group(6), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x0A,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='sami driver version')

        self._param_dict.add(Parameter.DEVICE1_SAMPLE_INTERVAL, configuration_string_regex,
                             lambda match: int(match.group(8), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x000000,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 1 sample interval')

        self._param_dict.add(Parameter.DEVICE1_DRIVER_VERSION, configuration_string_regex,
                             lambda match: int(match.group(9), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 1 driver version')

        self._param_dict.add(Parameter.DEVICE1_PARAMS_POINTER, configuration_string_regex,
                             lambda match: int(match.group(10), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 1 parameter pointer')

        self._param_dict.add(Parameter.NUMBER_SAMPLES_AVERAGED, configuration_string_regex,
                             lambda match: int(match.group(21), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x01,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of samples averaged')

        self._param_dict.add(Parameter.NUMBER_FLUSHES, configuration_string_regex,
                             lambda match: int(match.group(22), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x37,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of flushes')

        self._param_dict.add(Parameter.PUMP_ON_FLUSH, configuration_string_regex,
                             lambda match: int(match.group(23), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x04,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='pump on flush')

        self._param_dict.add(Parameter.PUMP_OFF_FLUSH, configuration_string_regex,
                             lambda match: int(match.group(24), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x20,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='pump off flush')

        self._param_dict.add(Parameter.NUMBER_REAGENT_PUMPS, configuration_string_regex,
                             lambda match: int(match.group(25), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x01,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of reagent pumps')

        self._param_dict.add(Parameter.VALVE_DELAY, configuration_string_regex,
                             lambda match: int(match.group(26), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x08,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='valve delay')

        self._param_dict.add(Parameter.PUMP_ON_IND, configuration_string_regex,
                             lambda match: int(match.group(27), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x08,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='pump on ind')

        self._param_dict.add(Parameter.PV_OFF_IND, configuration_string_regex,
                             lambda match: int(match.group(28), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x10,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='P/V off ind')

        self._param_dict.add(Parameter.NUMBER_BLANKS, configuration_string_regex,
                             lambda match: int(match.group(29), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x04,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of blanks')

        self._param_dict.add(Parameter.PUMP_MEASURE_T, configuration_string_regex,
                             lambda match: int(match.group(30), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x08,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='pump measure T')

        self._param_dict.add(Parameter.PUMP_OFF_TO_MEASURE, configuration_string_regex,
                             lambda match: int(match.group(31), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x10,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='pump off to measure')

        self._param_dict.add(Parameter.MEASURE_TO_PUMP_ON, configuration_string_regex,
                             lambda match: int(match.group(32), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x08,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='measure to pump on')

        self._param_dict.add(Parameter.NUMBER_MEASUREMENTS, configuration_string_regex,
                             lambda match: int(match.group(33), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x17,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='number of measurements')

        self._param_dict.add(Parameter.SALINITY_DELAY, configuration_string_regex,
                             lambda match: int(match.group(34), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=True,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_WRITE,
                             display_name='salinity delay')

    def _get_specific_configuration_string_parameters(self):
        log.debug('herb: ' + 'Protocol._build_configuration_string_specific()')

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
        return CONFIGURATION_REGEX
    def _get_configuration_string_regex_matcher(self):
        """
        Get config string regex matcher.
        @retval configuration string regex matcher
        """
        return CONFIGURATION_REGEX_MATCHER
    def _get_blank_sample_timeout(self):
        """
        Get blank sample timeout.
        @retval blank sample timeout in seconds.
        """
        return SAMPLE_DELAY
    def _get_sample_timeout(self):
        """
        Get sample timeout.
        @retval sample timeout in seconds.
        """
        return SAMPLE_DELAY
    def _get_sample_regex(self):
        """
        Get sample regex
        @retval sample regex
        """
        return SAMI_SAMPLE_REGEX_MATCHER

# End of File driver.py
