"""
@package mi.instrument.sunburst.sami2_ph.ooicore.driver
@file marine-integrations/mi/instrument/sunburst/sami2_ph/ooicore/driver.py
@author Stuart Pearce
@brief Driver for the ooicore
Release notes:

Sunburst Sensors SAMI2-PH pH underwater sensor
"""

__author__ = 'Stuart Pearce'
__license__ = 'Apache 2.0'

import re

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentProtocolException
#from mi.core.exceptions import InstrumentParameterException

from mi.core.common import BaseEnum
#from mi.core.instrument.instrument_driver import DriverEvent
#from mi.core.instrument.instrument_driver import DriverAsyncEvent
#from mi.core.instrument.instrument_driver import DriverProtocolState
#from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
#from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
#from mi.core.instrument.protocol_param_dict import FunctionParameter
from mi.instrument.sunburst.driver import SamiDataParticleType
from mi.instrument.sunburst.driver import ProtocolState
from mi.instrument.sunburst.driver import ProtocolEvent
from mi.instrument.sunburst.driver import Capability
from mi.instrument.sunburst.driver import SamiParameter
from mi.instrument.sunburst.driver import Prompt
from mi.instrument.sunburst.driver import SamiInstrumentCommand
# NOTE: These may not need to be imported [start]
from mi.instrument.sunburst.driver import SamiRegularStatusDataParticleKey
from mi.instrument.sunburst.driver import SamiControlRecordDataParticleKey
# [/stop]
from mi.instrument.sunburst.driver import SamiRegularStatusDataParticle
from mi.instrument.sunburst.driver import SamiControlRecordDataParticle
from mi.instrument.sunburst.driver import SamiConfigDataParticleKey
from mi.instrument.sunburst.driver import SamiInstrumentDriver
from mi.instrument.sunburst.driver import SamiProtocol
from mi.instrument.sunburst.driver import REGULAR_STATUS_REGEX_MATCHER
from mi.instrument.sunburst.driver import CONTROL_RECORD_REGEX_MATCHER
from mi.instrument.sunburst.driver import ERROR_REGEX_MATCHER
# newline.
from mi.instrument.sunburst.driver import NEWLINE

# default timeout.
from mi.instrument.sunburst.driver import TIMEOUT

# Epoch conversions (SAMI epoch Jan. 1, 1904) see sunburst driver for usage
from mi.instrument.sunburst.driver import SAMI_TO_UNIX
from mi.instrument.sunburst.driver import SAMI_TO_NTP

###
#    Driver Constant Definitions
###

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


class DataParticleType(SamiDataParticleType):
    """
    Data particle types produced by this driver
    """
    pass
    # The PCO2 driver should extend this with:
    #DEV1_SAMPLE = 'dev1_sample'


class Parameter(SamiParameter):
    """
    Device specific parameters.
    """
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

# NOTE: I don't think I need to subclass this one.
#class Prompt(BaseEnum):
#    """
#    Device i/o prompts..
#    """


class InstrumentCommand(SamiInstrumentCommand):
    """
    Device specfic Instrument command strings. Extends superclass
    SamiInstrumentCommand
    """
    pass
    # PCO2 Driver needs to add this statement to extend:
    #ACQUIRE_SAMPLE_DEV1 = 'R1'


###############################################################################
# Data Particles
###############################################################################

#class SamiRegularStatusDataParticleKey(BaseEnum):
#    """
#    Data particle key for the regular (1 Hz or polled) status messages.
#    """
#    ELAPSED_TIME_CONFIG = "elapsed_time_config"
#    CLOCK_ACTIVE = 'clock_active'
#    RECORDING_ACTIVE = 'recording_active'
#    RECORD_END_ON_TIME = 'record_end_on_time'
#    RECORD_MEMORY_FULL = 'record_memory_full'
#    RECORD_END_ON_ERROR = 'record_end_on_error'
#    DATA_DOWNLOAD_OK = 'data_download_ok'
#    FLASH_MEMORY_OPEN = 'flash_memory_open'
#    BATTERY_LOW_PRESTART = 'battery_low_prestart'
#    BATTERY_LOW_MEASUREMENT = 'battery_low_measurement'
#    BATTERY_LOW_BANK = 'battery_low_bank'
#    BATTERY_LOW_EXTERNAL = 'battery_low_external'
#    EXTERNAL_DEVICE1_FAULT = 'external_device1_fault'
#    EXTERNAL_DEVICE2_FAULT = 'external_device2_fault'
#    EXTERNAL_DEVICE3_FAULT = 'external_device3_fault'
#    FLASH_ERASED = 'flash_erased'
#    POWER_ON_INVALID = 'power_on_invalid'
#    NUM_DATA_RECORDS = 'num_data_records'
#    NUM_ERROR_RECORDS = 'num_error_records'
#    NUM_BYTES_STORED = 'num_bytes_stored'
#    CHECKSUM = 'checksum'

#class SamiRegularStatusDataParticle(DataParticle):
#    """
#    Routines for parsing raw data into an regular status data particle
#    structure.
#    @throw SampleException If there is a problem with sample creation
#    """
#    _data_particle_type = DataParticleType.REGULAR_STATUS
#
#    def _build_parsed_values(self):
#        """
#        Parse regular status values from raw data into a dictionary
#        """
#
#        matched = REGULAR_STATUS_REGEX_MATCHER.match(self.raw_data)
#        if not matched:
#            raise SampleException("No regex match of parsed sample data: [%s]" %
#                                  self.decoded_raw)
#
#        particle_keys = [SamiRegularStatusDataParticleKey.ELAPSED_TIME_CONFIG,
#                         SamiRegularStatusDataParticleKey.CLOCK_ACTIVE,
#                         SamiRegularStatusDataParticleKey.RECORDING_ACTIVE,
#                         SamiRegularStatusDataParticleKey.RECORD_END_ON_TIME,
#                         SamiRegularStatusDataParticleKey.RECORD_MEMORY_FULL,
#                         SamiRegularStatusDataParticleKey.RECORD_END_ON_ERROR,
#                         SamiRegularStatusDataParticleKey.DATA_DOWNLOAD_OK,
#                         SamiRegularStatusDataParticleKey.FLASH_MEMORY_OPEN,
#                         SamiRegularStatusDataParticleKey.BATTERY_LOW_PRESTART,
#                         SamiRegularStatusDataParticleKey.BATTERY_LOW_MEASUREMENT,
#                         SamiRegularStatusDataParticleKey.BATTERY_LOW_BANK,
#                         SamiRegularStatusDataParticleKey.BATTERY_LOW_EXTERNAL,
#                         SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE1_FAULT,
#                         SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE2_FAULT,
#                         SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE3_FAULT,
#                         SamiRegularStatusDataParticleKey.FLASH_ERASED,
#                         SamiRegularStatusDataParticleKey.POWER_ON_INVALID,
#                         SamiRegularStatusDataParticleKey.NUM_DATA_RECORDS,
#                         SamiRegularStatusDataParticleKey.NUM_ERROR_RECORDS,
#                         SamiRegularStatusDataParticleKey.NUM_BYTES_STORED,
#                         SamiRegularStatusDataParticleKey.CHECKSUM]
#
#        result = []
#        grp_index = 1
#        bit_index = 0
#
#        for key in particle_keys:
#            if key in [SamiRegularStatusDataParticleKey.CLOCK_ACTIVE,
#                       SamiRegularStatusDataParticleKey.RECORDING_ACTIVE,
#                       SamiRegularStatusDataParticleKey.RECORD_END_ON_TIME,
#                       SamiRegularStatusDataParticleKey.RECORD_MEMORY_FULL,
#                       SamiRegularStatusDataParticleKey.RECORD_END_ON_ERROR,
#                       SamiRegularStatusDataParticleKey.DATA_DOWNLOAD_OK,
#                       SamiRegularStatusDataParticleKey.FLASH_MEMORY_OPEN,
#                       SamiRegularStatusDataParticleKey.BATTERY_LOW_PRESTART,
#                       SamiRegularStatusDataParticleKey.BATTERY_LOW_MEASUREMENT,
#                       SamiRegularStatusDataParticleKey.BATTERY_LOW_BANK,
#                       SamiRegularStatusDataParticleKey.BATTERY_LOW_EXTERNAL,
#                       SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE1_FAULT,
#                       SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE2_FAULT,
#                       SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE3_FAULT,
#                       SamiRegularStatusDataParticleKey.FLASH_ERASED,
#                       SamiRegularStatusDataParticleKey.POWER_ON_INVALID]:
#                result.append({DataParticleKey.VALUE_ID: key,
#                               DataParticleKey.VALUE: bool(int(matched.group(2), 16) & (1 << bit_index))})
#                bit_index += 1
#                grp_index = 3
#            else:
#                result.append({DataParticleKey.VALUE_ID: key,
#                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
#                grp_index += 1
#
#        return result

# NOTE: This may not need to be imported.

#class SamiControlRecordDataParticleKey(BaseEnum):
#    """
#    Data particle key for peridoically produced control records.
#    """
#    UNIQUE_ID = 'unique_id'
#    RECORD_LENGTH = 'record_length'
#    RECORD_TYPE = 'record_type'
#    RECORD_TIME = 'record_time'
#    CLOCK_ACTIVE = 'clock_active'
#    RECORDING_ACTIVE = 'recording_active'
#    RECORD_END_ON_TIME = 'record_end_on_time'
#    RECORD_MEMORY_FULL = 'record_memory_full'
#    RECORD_END_ON_ERROR = 'record_end_on_error'
#    DATA_DOWNLOAD_OK = 'data_download_ok'
#    FLASH_MEMORY_OPEN = 'flash_memory_open'
#    BATTERY_LOW_PRESTART = 'battery_low_prestart'
#    BATTERY_LOW_MEASUREMENT = 'battery_low_measurement'
#    BATTERY_LOW_BANK = 'battery_low_bank'
#    BATTERY_LOW_EXTERNAL = 'battery_low_external'
#    EXTERNAL_DEVICE1_FAULT = 'external_device1_fault'
#    EXTERNAL_DEVICE2_FAULT = 'external_device2_fault'
#    EXTERNAL_DEVICE3_FAULT = 'external_device3_fault'
#    FLASH_ERASED = 'flash_erased'
#    POWER_ON_INVALID = 'power_on_invalid'
#    NUM_DATA_RECORDS = 'num_data_records'
#    NUM_ERROR_RECORDS = 'num_error_records'
#    NUM_BYTES_STORED = 'num_bytes_stored'
#    CHECKSUM = 'checksum'


#class SamiControlRecordDataParticle(DataParticle):
#    """
#    Routines for parsing raw data into a control record data particle
#    structure.
#    @throw SampleException If there is a problem with sample creation
#    """
#    _data_particle_type = DataParticleType.CONTROL_RECORD
#
#    def _build_parsed_values(self):
#        """
#        Parse control record values from raw data into a dictionary
#        """
#
#        matched = CONTROL_RECORD_REGEX_MATCHER.match(self.raw_data)
#        if not matched:
#            raise SampleException("No regex match of parsed sample data: [%s]" %
#                                  self.decoded_raw)
#
#        particle_keys = [SamiControlRecordDataParticleKey.UNIQUE_ID,
#                         SamiControlRecordDataParticleKey.RECORD_LENGTH,
#                         SamiControlRecordDataParticleKey.RECORD_TYPE,
#                         SamiControlRecordDataParticleKey.RECORD_TIME,
#                         SamiControlRecordDataParticleKey.CLOCK_ACTIVE,
#                         SamiControlRecordDataParticleKey.RECORDING_ACTIVE,
#                         SamiControlRecordDataParticleKey.RECORD_END_ON_TIME,
#                         SamiControlRecordDataParticleKey.RECORD_MEMORY_FULL,
#                         SamiControlRecordDataParticleKey.RECORD_END_ON_ERROR,
#                         SamiControlRecordDataParticleKey.DATA_DOWNLOAD_OK,
#                         SamiControlRecordDataParticleKey.FLASH_MEMORY_OPEN,
#                         SamiControlRecordDataParticleKey.BATTERY_LOW_PRESTART,
#                         SamiControlRecordDataParticleKey.BATTERY_LOW_MEASUREMENT,
#                         SamiControlRecordDataParticleKey.BATTERY_LOW_BANK,
#                         SamiControlRecordDataParticleKey.BATTERY_LOW_EXTERNAL,
#                         SamiControlRecordDataParticleKey.EXTERNAL_DEVICE1_FAULT,
#                         SamiControlRecordDataParticleKey.EXTERNAL_DEVICE2_FAULT,
#                         SamiControlRecordDataParticleKey.EXTERNAL_DEVICE3_FAULT,
#                         SamiControlRecordDataParticleKey.FLASH_ERASED,
#                         SamiControlRecordDataParticleKey.POWER_ON_INVALID,
#                         SamiControlRecordDataParticleKey.NUM_DATA_RECORDS,
#                         SamiControlRecordDataParticleKey.NUM_ERROR_RECORDS,
#                         SamiControlRecordDataParticleKey.NUM_BYTES_STORED,
#                         SamiControlRecordDataParticleKey.CHECKSUM]
#
#        result = []
#        grp_index = 1
#        bit_index = 0
#
#        for key in particle_keys:
#            if key in [SamiControlRecordDataParticleKey.CLOCK_ACTIVE,
#                       SamiControlRecordDataParticleKey.RECORDING_ACTIVE,
#                       SamiControlRecordDataParticleKey.RECORD_END_ON_TIME,
#                       SamiControlRecordDataParticleKey.RECORD_MEMORY_FULL,
#                       SamiControlRecordDataParticleKey.RECORD_END_ON_ERROR,
#                       SamiControlRecordDataParticleKey.DATA_DOWNLOAD_OK,
#                       SamiControlRecordDataParticleKey.FLASH_MEMORY_OPEN,
#                       SamiControlRecordDataParticleKey.BATTERY_LOW_PRESTART,
#                       SamiControlRecordDataParticleKey.BATTERY_LOW_MEASUREMENT,
#                       SamiControlRecordDataParticleKey.BATTERY_LOW_BANK,
#                       SamiControlRecordDataParticleKey.BATTERY_LOW_EXTERNAL,
#                       SamiControlRecordDataParticleKey.EXTERNAL_DEVICE1_FAULT,
#                       SamiControlRecordDataParticleKey.EXTERNAL_DEVICE2_FAULT,
#                       SamiControlRecordDataParticleKey.EXTERNAL_DEVICE3_FAULT,
#                       SamiControlRecordDataParticleKey.FLASH_ERASED,
#                       SamiControlRecordDataParticleKey.POWER_ON_INVALID]:
#                result.append({DataParticleKey.VALUE_ID: key,
#                               DataParticleKey.VALUE: bool(int(matched.group(5), 16) & (1 << bit_index))})
#                bit_index += 1
#                grp_index = 6
#            else:
#                result.append({DataParticleKey.VALUE_ID: key,
#                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
#                grp_index += 1
#
#        return result


class PhsenSamiSampleDataParticleKey(BaseEnum):
    """
    Data particle key for the SAMI2-PCO2 records. These particles
    capture when a sample was processed.
    """
    UNIQUE_ID = 'unique_id'
    RECORD_LENGTH = 'record_length'
    RECORD_TYPE = 'record_type'
    RECORD_TIME = 'record_time'
    START_THERMISTOR = 'thermistor_start'
    REF_MEASUREMENTS = 'reference_light_measurements'
    PH_MEASUREMENTS = 'light_measurements'
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
        grp_index = 1
        unhex = lambda x: int(x, 16)
        # ref_measurements
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
        SamiProtocol.__init__(self, prompts, newline, driver_event)

        ## Build protocol state machine.
        #self._protocol_fsm = InstrumentFSM(
        #    ProtocolState, ProtocolEvent,
        #    ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        ## Add event handlers for protocol state machine
        #self._protocol_fsm.add_handler(
        #    ProtocolState.UNKNOWN, ProtocolEvent.ENTER,
        #    self._handler_unknown_enter)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.UNKNOWN, ProtocolEvent.EXIT,
        #    self._handler_unknown_exit)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER,
        #    self._handler_unknown_discover)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.UNKNOWN, ProtocolEvent.START_DIRECT,
        #    self._handler_command_start_direct)

        #self._protocol_fsm.add_handler(
        #    ProtocolState.COMMAND, ProtocolEvent.ENTER,
        #    self._handler_command_enter)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.COMMAND, ProtocolEvent.EXIT,
        #    self._handler_command_exit)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.COMMAND, ProtocolEvent.GET,
        #    self._handler_command_get)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.COMMAND, ProtocolEvent.SET,
        #    self._handler_command_set)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.COMMAND, ProtocolEvent.START_DIRECT,
        #    self._handler_command_start_direct)
        ### May be unneccessary
        ##self._protocol_fsm.add_handler(
        ##    ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_CONFIGURATION,
        ##    self._handler_command_acquire_configuration)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS,
        #    self._handler_command_acquire_status)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE,
        #    self._handler_command_acquire_sample)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE,
        #    self._handler_command_start_autosample)

        #self._protocol_fsm.add_handler(
        #    ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER,
        #    self._handler_direct_access_enter)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT,
        #    self._handler_direct_access_exit)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT,
        #    self._handler_direct_access_stop_direct)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT,
        #    self._handler_direct_access_execute_direct)

        #self._protocol_fsm.add_handler(
        #    ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER,
        #    self._handler_autosample_enter)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT,
        #    self._handler_autosample_exit)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE,
        #    self._handler_autosample_stop)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_SAMPLE,
        #    self._handler_autosample_acquire_sample)

        ## this state would be entered whenever an ACQUIRE_SAMPLE event occurred
        ## while in the AUTOSAMPLE state and will last anywhere from 10 seconds
        ## to 3 minutes depending on instrument and the type of sampling.
        #self._protocol_fsm.add_handler(
        #    ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.ENTER,
        #    self._handler_scheduled_sample_enter)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.EXIT,
        #    self._handler_scheduled_sample_exit)
        self._protocol_fsm.add_handler(
            ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.SUCCESS,
            self._handler_sample_success)
        self._protocol_fsm.add_handler(
            ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.TIMEOUT,
            self._handler_sample_timeout)

        ## this state would be entered whenever an ACQUIRE_SAMPLE event occurred
        ## while in either the COMMAND state (or via the discover transition
        ## from the UNKNOWN state with the instrument unresponsive) and will
        ## last anywhere from a few seconds to 3 minutes depending on instrument
        ## and sample type.
        #self._protocol_fsm.add_handler(
        #    ProtocolState.POLLED_SAMPLE, ProtocolEvent.ENTER,
        #    self._handler_polled_sample_enter)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.POLLED_SAMPLE, ProtocolEvent.EXIT,
        #    self._handler_polled_sample_exit)
        self._protocol_fsm.add_handler(
            ProtocolState.POLLED_SAMPLE, ProtocolEvent.SUCCESS,
            self._handler_sample_success)
        self._protocol_fsm.add_handler(
            ProtocolState.POLLED_SAMPLE, ProtocolEvent.TIMEOUT,
            self._handler_sample_timeout)

        ## Construct the parameter dictionary containing device parameters,
        ## current parameter values, and set formatting functions.
        #self._build_param_dict()
        #self._build_command_dict()
        #self._build_driver_dict()

        ## Add build handlers for device commands.
        # Add this statement in the Protocol.__init__ method in the Pco2 driver
        #self._add_build_handler(InstrumentCommand.ACQUIRE_SAMPLE_DEV1, self._build_sample_dev1)

        ## Add response handlers for device commands.
        # Add this statement in the Protocol.__init__ method in the Pco2 driver
        #self._add_response_handler(InstrumentCommand.ACQUIRE_SAMPLE_DEV1, self._build_response_sample_dev1)

        # Add sample handlers.

        # ?? Base driver or sub driver ??
        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # ?? Base driver or sub driver ??
        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        # something about the chunker
        self._chunker = StringChunker(Protocol.sieve_function)

    # NOTE: it turns out that sieve_function needs to remain in the sub driver
    # since it is a static method and could not pass sieve_matchers well.
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

    # NOTE: I think kept here in the sub driver
    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        self._extract_sample(SamiRegularStatusDataParticle, REGULAR_STATUS_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(SamiControlRecordDataParticle, CONTROL_RECORD_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(PhsenSamiSampleDataParticle, SAMI_SAMPLE_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(PhsenConfigDataParticle, CONFIGURATION_REGEX_MATCHER, chunk, timestamp)

    #def _filter_capabilities(self, events):
    #    """
    #    Return a list of currently available capabilities.
    #    """
    #    return [x for x in events if Capability.has(x)]

    #########################################################################
    ## Unknown handlers.
    #########################################################################
    #
    #def _handler_unknown_enter(self, *args, **kwargs):
    #    """
    #    Enter unknown state.
    #    """
    #    # Tell driver superclass to send a state change event.
    #    # Superclass will query the state.
    #    self._driver_event(DriverAsyncEvent.STATE_CHANGE)
    #
    #def _handler_unknown_exit(self, *args, **kwargs):
    #    """
    #    Exit unknown state.
    #    """
    #    pass
    #
    #def _handler_unknown_discover(self, *args, **kwargs):
    #    """
    #    Discover current state
    #    @retval (next_state, result)
    #    """
    #    return (ProtocolState.COMMAND, ResourceAgentState.IDLE)

    #########################################################################
    ## Command handlers.
    #########################################################################
    #
    #def _handler_command_enter(self, *args, **kwargs):
    #    """
    #    Enter command state.
    #    @throws InstrumentTimeoutException if the device cannot be woken.
    #    @throws InstrumentProtocolException if the update commands and not recognized.
    #    """
    #    # Command device to update parameters and send a config change event.
    #    #self._update_params()
    #
    #    # Tell driver superclass to send a state change event.
    #    # Superclass will query the state.
    #    self._driver_event(DriverAsyncEvent.STATE_CHANGE)
    #
    #def _handler_command_exit(self, *args, **kwargs):
    #    """
    #    Exit command state.
    #    """
    #    pass
    #
    #def _handler_command_get(self, *args, **kwargs):
    #    """
    #    Get parameter
    #    """
    #    next_state = None
    #    result = None
    #
    #    return (next_state, result)
    #
    #def _handler_command_set(self, *args, **kwargs):
    #    """
    #    Set parameter
    #    """
    #    next_state = None
    #    result = None
    #
    #    return (next_state, result)
    #
    #def _handler_command_start_direct(self):
    #    """
    #    Start direct access
    #    """
    #    next_state = ProtocolState.DIRECT_ACCESS
    #    next_agent_state = ResourceAgentState.DIRECT_ACCESS
    #    result = None
    #    log.debug("_handler_command_start_direct: entering DA mode")
    #    return (next_state, (next_agent_state, result))
    #
    #def _handler_command_acquire_configuration(self, *args, **kwargs):
    #    """
    #    Acquire the instrument's configuration
    #    """
    #    next_state = None
    #    result = None
    #
    #    return (next_state, result)
    #
    #def _handler_command_acquire_status(self, *args, **kwargs):
    #    """
    #    Acquire the instrument's status
    #    """
    #    next_state = None
    #    result = None
    #
    #    return (next_state, result)
    #
    #def _handler_command_acquire_sample(self, *args, **kwargs):
    #    """
    #    Acquire a sample
    #    """
    #    next_state = None
    #    result = None
    #
    #    return (next_state, result)
    #
    #def _handler_command_start_autosample(self, *args, **kwargs):
    #    """
    #    Start autosample mode (spoofed via use of scheduler)
    #    """
    #    next_state = None
    #    result = None
    #
    #    return (next_state, result)

    #########################################################################
    ## Direct access handlers.
    #########################################################################
    #
    #def _handler_direct_access_enter(self, *args, **kwargs):
    #    """
    #    Enter direct access state.
    #    """
    #    # Tell driver superclass to send a state change event.
    #    # Superclass will query the state.
    #    self._driver_event(DriverAsyncEvent.STATE_CHANGE)
    #
    #    self._sent_cmds = []
    #
    #def _handler_direct_access_exit(self, *args, **kwargs):
    #    """
    #    Exit direct access state.
    #    """
    #    pass
    #
    #def _handler_direct_access_execute_direct(self, data):
    #    """
    #    """
    #    next_state = None
    #    result = None
    #    next_agent_state = None
    #
    #    self._do_cmd_direct(data)
    #
    #    # add sent command to list for 'echo' filtering in callback
    #    self._sent_cmds.append(data)
    #
    #    return (next_state, (next_agent_state, result))
    #
    #def _handler_direct_access_stop_direct(self):
    #    """
    #    @throw InstrumentProtocolException on invalid command
    #    """
    #    next_state = None
    #    result = None
    #
    #    next_state = ProtocolState.COMMAND
    #    next_agent_state = ResourceAgentState.COMMAND
    #
    #    return (next_state, (next_agent_state, result))

    #########################################################################
    ## Autosample handlers.
    #########################################################################
    #
    #def _handler_autosample_enter(self, ):
    #    """
    #    Enter Autosample state
    #    """
    #    # Tell driver superclass to send a state change event.
    #    # Superclass will query the state.
    #    self._driver_event(DriverAsyncEvent.STATE_CHANGE)
    #
    #    self._sent_cmds = []
    #
    #def _handler_autosample_exit(self, *args, **kwargs):
    #    """
    #    Exit autosample state
    #    """
    #    pass
    #
    #def _handler_autosample_stop(self, *args, **kwargs):
    #    """
    #    Stop autosample
    #    """
    #    next_state = None
    #    result = None
    #
    #    return (next_state, result)
    #
    #def _handler_autosample_acquire_sample(self, *args, **kwargs):
    #    """
    #    While in autosample mode, poll for samples using the scheduler
    #    """
    #    next_state = None
    #    result = None
    #
    #    return (next_state, result)

    #########################################################################
    ## Scheduled Sample handlers.
    #########################################################################
    #
    #def _handler_scheduled_sample_enter(self, *args, **kwargs):
    #    """
    #    Enter busy state.
    #    """
    #    # Tell driver superclass to send a state change event.
    #    # Superclass will query the state.
    #    self._driver_event(DriverAsyncEvent.STATE_CHANGE)
    #
    #    self._sent_cmds = []
    #
    #def _handler_scheduled_sample_exit(self, *args, **kwargs):
    #    """
    #    Exit busy state.
    #    """
    #    pass

    #########################################################################
    ## Polled Sample handlers.
    #########################################################################
    #
    #def _handler_polled_sample_enter(self, *args, **kwargs):
    #    """
    #    Enter busy state.
    #    """
    #    # Tell driver superclass to send a state change event.
    #    # Superclass will query the state.
    #    self._driver_event(DriverAsyncEvent.STATE_CHANGE)
    #
    #    self._sent_cmds = []
    #
    #def _handler_polled_sample_exit(self, *args, **kwargs):
    #    """
    #    Exit busy state.
    #    """
    #    pass

    #########################################################################
    ## General (for POLLED and SCHEDULED states) Sample handlers.
    #########################################################################

    def _handler_sample_success(self, *args, **kwargs):
        next_state = None
        result = None

        return (next_state, result)

    def _handler_sample_timeout(self, ):
        next_state = None
        result = None

        return (next_state, result)

    ####################################################################
    # Build Command & Parameter dictionary
    ####################################################################

    #def _build_command_dict(self):
    #    """
    #    Populate the command dictionary with command.
    #    """
    #    self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name="acquire status")
    #    self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="start autosample")
    #    self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="stop autosample")
    #    self._cmd_dict.add(Capability.START_DIRECT, display_name="start direct access")
    #    self._cmd_dict.add(Capability.STOP_DIRECT, display_name="stop direct access")
    #
    #def _build_driver_dict(self):
    #    """
    #    Populate the driver dictionary with options
    #    """
    #    self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        self._param_dict = ProtocolParameterDict()

        self._param_dict.add(Parameter.LAUNCH_TIME, CONFIGURATION_REGEX,
                             lambda match: int(match.group(1), 16),
                             lambda x: self._int_to_hexstring(x, 8),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00000000,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='launch time')

        self._param_dict.add(Parameter.START_TIME_FROM_LAUNCH, CONFIGURATION_REGEX,
                             lambda match: int(match.group(2), 16),
                             lambda x: self._int_to_hexstring(x, 8),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x02C7EA00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='start time after launch time')

        self._param_dict.add(Parameter.STOP_TIME_FROM_START, CONFIGURATION_REGEX,
                             lambda match: int(match.group(3), 16),
                             lambda x: self._int_to_hexstring(x, 8),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x01E13380,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='stop time after start time')

        self._param_dict.add(Parameter.MODE_BITS, CONFIGURATION_REGEX,
                             lambda match: int(match.group(4), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x0A,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='mode bits (set to 00001010)')

        self._param_dict.add(Parameter.SAMI_SAMPLE_INTERVAL, CONFIGURATION_REGEX,
                             lambda match: int(match.group(5), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x000E10,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='sami sample interval')

        self._param_dict.add(Parameter.SAMI_DRIVER_VERSION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(6), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x04,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='sami driver version')

        self._param_dict.add(Parameter.SAMI_PARAMS_POINTER, CONFIGURATION_REGEX,
                             lambda match: int(match.group(7), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x02,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='sami parameter pointer')

        self._param_dict.add(Parameter.DEVICE1_SAMPLE_INTERVAL, CONFIGURATION_REGEX,
                             lambda match: int(match.group(8), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x000E10,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 1 sample interval')

        self._param_dict.add(Parameter.DEVICE1_DRIVER_VERSION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(9), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x01,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 1 driver version')

        self._param_dict.add(Parameter.DEVICE1_PARAMS_POINTER, CONFIGURATION_REGEX,
                             lambda match: int(match.group(10), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x0B,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 1 parameter pointer')

        self._param_dict.add(Parameter.DEVICE2_SAMPLE_INTERVAL, CONFIGURATION_REGEX,
                             lambda match: int(match.group(11), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x000000,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 2 sample interval')

        self._param_dict.add(Parameter.DEVICE2_DRIVER_VERSION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(12), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 2 driver version')

        self._param_dict.add(Parameter.DEVICE2_PARAMS_POINTER, CONFIGURATION_REGEX,
                             lambda match: int(match.group(13), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x0D,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 2 parameter pointer')

        self._param_dict.add(Parameter.DEVICE3_SAMPLE_INTERVAL, CONFIGURATION_REGEX,
                             lambda match: int(match.group(14), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x000000,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 3 sample interval')

        self._param_dict.add(Parameter.DEVICE3_DRIVER_VERSION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(15), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 3 driver version')

        self._param_dict.add(Parameter.DEVICE3_PARAMS_POINTER, CONFIGURATION_REGEX,
                             lambda match: int(match.group(16), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x0D,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='device 3 parameter pointer')

        self._param_dict.add(Parameter.PRESTART_SAMPLE_INTERVAL, CONFIGURATION_REGEX,
                             lambda match: int(match.group(17), 16),
                             lambda x: self._int_to_hexstring(x, 6),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x000000,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='prestart sample interval')

        self._param_dict.add(Parameter.PRESTART_DRIVER_VERSION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(18), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='prestart driver version')

        self._param_dict.add(Parameter.PRESTART_PARAMS_POINTER, CONFIGURATION_REGEX,
                             lambda match: int(match.group(19), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x0D,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='prestart parameter pointer')

        self._param_dict.add(Parameter.GLOBAL_CONFIGURATION, CONFIGURATION_REGEX,
                             lambda match: int(match.group(20), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='global bits (set to 00000111)')

        self._param_dict.add(Parameter.NUMBER_SAMPLES_AVERAGED, CONFIGURATION_REGEX,
                             lambda match: int(match.group(21), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.NUMBER_FLUSHES, CONFIGURATION_REGEX,
                             lambda match: int(match.group(22), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.PUMP_ON_FLUSH, CONFIGURATION_REGEX,
                             lambda match: int(match.group(23), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.PUMP_OFF_FLUSH, CONFIGURATION_REGEX,
                             lambda match: int(match.group(24), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.NUMBER_REAGENT_PUMPS, CONFIGURATION_REGEX,
                             lambda match: int(match.group(25), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.VALVE_DELAY, CONFIGURATION_REGEX,
                             lambda match: int(match.group(26), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.PUMP_ON_IND, CONFIGURATION_REGEX,
                             lambda match: int(match.group(27), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.PV_OFF_IND, CONFIGURATION_REGEX,
                             lambda match: int(match.group(28), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.NUMBER_BLANKS, CONFIGURATION_REGEX,
                             lambda match: int(match.group(29), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.PUMP_MEASURE_T, CONFIGURATION_REGEX,
                             lambda match: int(match.group(30), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.PUMP_OFF_TO_MEASURE, CONFIGURATION_REGEX,
                             lambda match: int(match.group(31), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.MEASURE_TO_PUMP_ON, CONFIGURATION_REGEX,
                             lambda match: int(match.group(32), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.NUMBER_MEASUREMENTS, CONFIGURATION_REGEX,
                             lambda match: int(match.group(33), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

        self._param_dict.add(Parameter.SALINITY_DELAY, CONFIGURATION_REGEX,
                             lambda match: int(match.group(34), 16),
                             lambda x: self._int_to_hexstring(x, 2),
                             type=ParameterDictType.INT,
                             startup_param=False,
                             direct_access=True,
                             default_value=0x00,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             display_name='number of samples averaged',
                             description='')

# End of File driver.py