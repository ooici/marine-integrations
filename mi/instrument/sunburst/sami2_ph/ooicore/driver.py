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
import string
import datetime as dt

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.chunker import StringChunker


# newline.
NEWLINE = '\r'

# default timeout.
TIMEOUT = 10

# Conversion from SAMI time (seconds since 1904-01-01) to POSIX or Unix
# timestamps (seconds since 1970-01-01). Add this value to convert POSIX
# timestamps to SAMI, and subtract for the reverse.
SAMI_TO_UNIX = 2082844800
SAMI_TO_NTP = (dt.datetime(1904, 1, 1) - dt.datetime(1900, 1, 1)).total_seconds()

###
#    Driver Constant Definitions
###

###
#    Driver RegEx Definitions
###

# Regular Status Strings (produced every 1 Hz or in response to S0 command)
REGULAR_STATUS_REGEX = (
    r'[:]' +  # status message identifier
    '([0-9A-Fa-f]{8})' +  # timestamp (seconds since 1904)
    '([0-9A-Fa-f]{4})' +  # status bit field
    '([0-9A-Fa-f]{6})' +  # number of data records recorded
    '([0-9A-Fa-f]{6})' +  # number of errors
    '([0-9A-Fa-f]{6})' +  # number of bytes stored
    '([0-9A-Fa-f]{2})' +  # checksum
    NEWLINE)
REGULAR_STATUS_REGEX_MATCHER = re.compile(REGULAR_STATUS_REGEX)

# Control Records (Types 0x80 - 0xFF)
CONTROL_RECORD_REGEX = (
    r'[\*]' +  # record identifier
    '([0-9A-Fa-f]{2})' +  # unique instrument identifier
    '([0-9A-Fa-f]{2})' +  # control record length (bytes)
    '([8-9A-Fa-f][0-9A-Fa-f])' +  # type of control record 0x80-FF
    '([0-9A-Fa-f]{8})' +  # timestamp (seconds since 1904)
    '([0-9A-Fa-f]{4})' +  # status bit field
    '([0-9A-Fa-f]{6})' +  # number of data records recorded
    '([0-9A-Fa-f]{6})' +  # number of errors
    '([0-9A-Fa-f]{6})' +  # number of bytes stored
    '([0-9A-Fa-f]{2})' +  # checksum
    NEWLINE)
CONTROL_RECORD_REGEX_MATCHER = re.compile(CONTROL_RECORD_REGEX)

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

# Error records
ERROR_REGEX = r'[?]([0-9A-Fa-f]{2})' + NEWLINE
ERROR_REGEX_MATCHER = re.compile(ERROR_REGEX)


###
#    Begin Classes
###
class DataParticleType(BaseEnum):
    """
    Data particle types produced by this driver
    """
    RAW = CommonDataParticleType.RAW
    REGULAR_STATUS = 'regular_status'
    CONTROL_RECORD = 'control_record'
    SAMI_SAMPLE = 'sami_sample'
    CONFIGURATION = 'configuration'
    ERROR_CODE = 'error_code'


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
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS


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


# [TODO: This needs to be moved to the baseclass]
class SamiRegularStatusDataParticleKey(BaseEnum):
    """
    Data particle key for the regular (1 Hz or polled) status messages.
    """
    ELAPSED_TIME_CONFIG = "elapsed_time_config"
    CLOCK_ACTIVE = 'clock_active'
    RECORDING_ACTIVE = 'recording_active'
    RECORD_END_ON_TIME = 'record_end_on_time'
    RECORD_MEMORY_FULL = 'record_memory_full'
    RECORD_END_ON_ERROR = 'record_end_on_error'
    DATA_DOWNLOAD_OK = 'data_download_ok'
    FLASH_MEMORY_OPEN = 'flash_memory_open'
    BATTERY_LOW_PRESTART = 'battery_low_prestart'
    BATTERY_LOW_MEASUREMENT = 'battery_low_measurement'
    BATTERY_LOW_BANK = 'battery_low_bank'
    BATTERY_LOW_EXTERNAL = 'battery_low_external'
    EXTERNAL_DEVICE1_FAULT = 'external_device1_fault'
    EXTERNAL_DEVICE2_FAULT = 'external_device2_fault'
    EXTERNAL_DEVICE3_FAULT = 'external_device3_fault'
    FLASH_ERASED = 'flash_erased'
    POWER_ON_INVALID = 'power_on_invalid'
    NUM_DATA_RECORDS = 'num_data_records'
    NUM_ERROR_RECORDS = 'num_error_records'
    NUM_BYTES_STORED = 'num_bytes_stored'
    CHECKSUM = 'checksum'


class SamiRegularStatusDataParticle(DataParticle):
    """
    Routines for parsing raw data into an regular status data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """
    _data_particle_type = DataParticleType.REGULAR_STATUS

    def _build_parsed_values(self):
        """
        Parse regular status values from raw data into a dictionary
        """

        matched = REGULAR_STATUS_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [SamiRegularStatusDataParticleKey.ELAPSED_TIME_CONFIG,
                         SamiRegularStatusDataParticleKey.CLOCK_ACTIVE,
                         SamiRegularStatusDataParticleKey.RECORDING_ACTIVE,
                         SamiRegularStatusDataParticleKey.RECORD_END_ON_TIME,
                         SamiRegularStatusDataParticleKey.RECORD_MEMORY_FULL,
                         SamiRegularStatusDataParticleKey.RECORD_END_ON_ERROR,
                         SamiRegularStatusDataParticleKey.DATA_DOWNLOAD_OK,
                         SamiRegularStatusDataParticleKey.FLASH_MEMORY_OPEN,
                         SamiRegularStatusDataParticleKey.BATTERY_LOW_PRESTART,
                         SamiRegularStatusDataParticleKey.BATTERY_LOW_MEASUREMENT,
                         SamiRegularStatusDataParticleKey.BATTERY_LOW_BANK,
                         SamiRegularStatusDataParticleKey.BATTERY_LOW_EXTERNAL,
                         SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE1_FAULT,
                         SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE2_FAULT,
                         SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE3_FAULT,
                         SamiRegularStatusDataParticleKey.FLASH_ERASED,
                         SamiRegularStatusDataParticleKey.POWER_ON_INVALID,
                         SamiRegularStatusDataParticleKey.NUM_DATA_RECORDS,
                         SamiRegularStatusDataParticleKey.NUM_ERROR_RECORDS,
                         SamiRegularStatusDataParticleKey.NUM_BYTES_STORED,
                         SamiRegularStatusDataParticleKey.CHECKSUM]

        result = []
        grp_index = 1
        bit_index = 0

        for key in particle_keys:
            if key in [SamiRegularStatusDataParticleKey.CLOCK_ACTIVE,
                       SamiRegularStatusDataParticleKey.RECORDING_ACTIVE,
                       SamiRegularStatusDataParticleKey.RECORD_END_ON_TIME,
                       SamiRegularStatusDataParticleKey.RECORD_MEMORY_FULL,
                       SamiRegularStatusDataParticleKey.RECORD_END_ON_ERROR,
                       SamiRegularStatusDataParticleKey.DATA_DOWNLOAD_OK,
                       SamiRegularStatusDataParticleKey.FLASH_MEMORY_OPEN,
                       SamiRegularStatusDataParticleKey.BATTERY_LOW_PRESTART,
                       SamiRegularStatusDataParticleKey.BATTERY_LOW_MEASUREMENT,
                       SamiRegularStatusDataParticleKey.BATTERY_LOW_BANK,
                       SamiRegularStatusDataParticleKey.BATTERY_LOW_EXTERNAL,
                       SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE1_FAULT,
                       SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE2_FAULT,
                       SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE3_FAULT,
                       SamiRegularStatusDataParticleKey.FLASH_ERASED,
                       SamiRegularStatusDataParticleKey.POWER_ON_INVALID]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(2), 16) & (1 << bit_index))})
                bit_index += 1
                grp_index = 3
            else:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
                grp_index += 1

        return result


# [TODO: This needs to be moved to the baseclass]
class SamiControlRecordDataParticleKey(BaseEnum):
    """
    Data particle key for peridoically produced control records.
    """
    UNIQUE_ID = 'unique_id'
    RECORD_LENGTH = 'record_length'
    RECORD_TYPE = 'record_type'
    RECORD_TIME = 'record_time'
    CLOCK_ACTIVE = 'clock_active'
    RECORDING_ACTIVE = 'recording_active'
    RECORD_END_ON_TIME = 'record_end_on_time'
    RECORD_MEMORY_FULL = 'record_memory_full'
    RECORD_END_ON_ERROR = 'record_end_on_error'
    DATA_DOWNLOAD_OK = 'data_download_ok'
    FLASH_MEMORY_OPEN = 'flash_memory_open'
    BATTERY_LOW_PRESTART = 'battery_low_prestart'
    BATTERY_LOW_MEASUREMENT = 'battery_low_measurement'
    BATTERY_LOW_BANK = 'battery_low_bank'
    BATTERY_LOW_EXTERNAL = 'battery_low_external'
    EXTERNAL_DEVICE1_FAULT = 'external_device1_fault'
    EXTERNAL_DEVICE2_FAULT = 'external_device2_fault'
    EXTERNAL_DEVICE3_FAULT = 'external_device3_fault'
    FLASH_ERASED = 'flash_erased'
    POWER_ON_INVALID = 'power_on_invalid'
    NUM_DATA_RECORDS = 'num_data_records'
    NUM_ERROR_RECORDS = 'num_error_records'
    NUM_BYTES_STORED = 'num_bytes_stored'
    CHECKSUM = 'checksum'


# [TODO: This needs to be moved to the baseclass]
class SamiControlRecordDataParticle(DataParticle):
    """
    Routines for parsing raw data into a control record data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """
    _data_particle_type = DataParticleType.CONTROL_RECORD

    def _build_parsed_values(self):
        """
        Parse control record values from raw data into a dictionary
        """

        matched = CONTROL_RECORD_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [SamiControlRecordDataParticleKey.UNIQUE_ID,
                         SamiControlRecordDataParticleKey.RECORD_LENGTH,
                         SamiControlRecordDataParticleKey.RECORD_TYPE,
                         SamiControlRecordDataParticleKey.RECORD_TIME,
                         SamiControlRecordDataParticleKey.CLOCK_ACTIVE,
                         SamiControlRecordDataParticleKey.RECORDING_ACTIVE,
                         SamiControlRecordDataParticleKey.RECORD_END_ON_TIME,
                         SamiControlRecordDataParticleKey.RECORD_MEMORY_FULL,
                         SamiControlRecordDataParticleKey.RECORD_END_ON_ERROR,
                         SamiControlRecordDataParticleKey.DATA_DOWNLOAD_OK,
                         SamiControlRecordDataParticleKey.FLASH_MEMORY_OPEN,
                         SamiControlRecordDataParticleKey.BATTERY_LOW_PRESTART,
                         SamiControlRecordDataParticleKey.BATTERY_LOW_MEASUREMENT,
                         SamiControlRecordDataParticleKey.BATTERY_LOW_BANK,
                         SamiControlRecordDataParticleKey.BATTERY_LOW_EXTERNAL,
                         SamiControlRecordDataParticleKey.EXTERNAL_DEVICE1_FAULT,
                         SamiControlRecordDataParticleKey.EXTERNAL_DEVICE2_FAULT,
                         SamiControlRecordDataParticleKey.EXTERNAL_DEVICE3_FAULT,
                         SamiControlRecordDataParticleKey.FLASH_ERASED,
                         SamiControlRecordDataParticleKey.POWER_ON_INVALID,
                         SamiControlRecordDataParticleKey.NUM_DATA_RECORDS,
                         SamiControlRecordDataParticleKey.NUM_ERROR_RECORDS,
                         SamiControlRecordDataParticleKey.NUM_BYTES_STORED,
                         SamiControlRecordDataParticleKey.CHECKSUM]

        result = []
        grp_index = 1
        bit_index = 0

        for key in particle_keys:
            if key in [SamiControlRecordDataParticleKey.CLOCK_ACTIVE,
                       SamiControlRecordDataParticleKey.RECORDING_ACTIVE,
                       SamiControlRecordDataParticleKey.RECORD_END_ON_TIME,
                       SamiControlRecordDataParticleKey.RECORD_MEMORY_FULL,
                       SamiControlRecordDataParticleKey.RECORD_END_ON_ERROR,
                       SamiControlRecordDataParticleKey.DATA_DOWNLOAD_OK,
                       SamiControlRecordDataParticleKey.FLASH_MEMORY_OPEN,
                       SamiControlRecordDataParticleKey.BATTERY_LOW_PRESTART,
                       SamiControlRecordDataParticleKey.BATTERY_LOW_MEASUREMENT,
                       SamiControlRecordDataParticleKey.BATTERY_LOW_BANK,
                       SamiControlRecordDataParticleKey.BATTERY_LOW_EXTERNAL,
                       SamiControlRecordDataParticleKey.EXTERNAL_DEVICE1_FAULT,
                       SamiControlRecordDataParticleKey.EXTERNAL_DEVICE2_FAULT,
                       SamiControlRecordDataParticleKey.EXTERNAL_DEVICE3_FAULT,
                       SamiControlRecordDataParticleKey.FLASH_ERASED,
                       SamiControlRecordDataParticleKey.POWER_ON_INVALID]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(5), 16) & (1 << bit_index))})
                bit_index += 1
                grp_index = 6
            else:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
                grp_index += 1

        return result


# [TODO: This needs to be moved to the baseclass]
class SamiErrorCodeDataParticleKey(BaseEnum):
    """
    Data particle key for the error code records.
    """
    ERROR_CODE = 'error_code'


# [TODO: This needs to be moved to the baseclass]
class SamiErrorCodeDataParticle(DataParticle):
    """
    Routines for parsing raw data into an error code data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """
    _data_particle_type = DataParticleType.ERROR_CODE

    def _build_parsed_values(self):
        """
        Parse error_code values from raw data into a dictionary
        """

        matched = ERROR_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [SamiErrorCodeDataParticleKey.ERROR_CODE]

        result = []
        grp_index = 1
        for key in particle_keys:
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
            grp_index += 1

        return result


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


class PhsenConfigDataParticleKey(BaseEnum):
    """
    Data particle key for the configuration record.
    """
    LAUNCH_TIME = 'launch_time'
    START_TIME_OFFSET = 'start_time_offset'
    RECORDING_TIME = 'recording_time'
    PMI_SAMPLE_SCHEDULE = 'pmi_sample_schedule'
    SAMI_SAMPLE_SCHEDULE = 'sami_sample_schedule'
    SLOT1_FOLLOWS_SAMI_SCHEDULE = 'slot1_follows_sami_schedule'
    SLOT1_INDEPENDENT_SCHEDULE = 'slot1_independent_schedule'
    SLOT2_FOLLOWS_SAMI_SCHEDULE = 'slot2_follows_sami_schedule'
    SLOT2_INDEPENDENT_SCHEDULE = 'slot2_independent_schedule'
    SLOT3_FOLLOWS_SAMI_SCHEDULE = 'slot3_follows_sami_schedule'
    SLOT3_INDEPENDENT_SCHEDULE = 'slot3_independent_schedule'
    TIMER_INTERVAL_SAMI = 'timer_interval_sami'
    DRIVER_ID_SAMI = 'driver_id_sami'
    PARAMETER_POINTER_SAMI = 'parameter_pointer_sami'
    TIMER_INTERVAL_DEVICE1 = 'timer_interval_device1'
    DRIVER_ID_DEVICE1 = 'driver_id_device1'
    PARAMETER_POINTER_DEVICE1 = 'parameter_pointer_device1'
    TIMER_INTERVAL_DEVICE2 = 'timer_interval_device2'
    DRIVER_ID_DEVICE2 = 'driver_id_device2'
    PARAMETER_POINTER_DEVICE2 = 'parameter_pointer_device2'
    TIMER_INTERVAL_DEVICE3 = 'timer_interval_device3'
    DRIVER_ID_DEVICE3 = 'driver_id_device3'
    PARAMETER_POINTER_DEVICE3 = 'parameter_pointer_device3'
    TIMER_INTERVAL_PRESTART = 'timer_interval_prestart'
    DRIVER_ID_PRESTART = 'driver_id_prestart'
    PARAMETER_POINTER_PRESTART = 'parameter_pointer_prestart'
    USE_BAUD_RATE_57600 = 'use_baud_rate_57600'
    SEND_RECORD_TYPE = 'send_record_type'
    SEND_LIVE_RECORDS = 'send_live_records'
    EXTEND_GLOBAL_CONFIG = 'extend_global_config'
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

        sieve_matchers = [REGULAR_STATUS_REGEX_MATCHER,
                          CONTROL_RECORD_REGEX_MATCHER,
                          SAMI_SAMPLE_REGEX_MATCHER,
                          CONFIGURATION_REGEX_MATCHER,
                          ERROR_REGEX_MATCHER]

        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.

    def _got_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
        with the appropriate particle objects and REGEXes.
        """
        self._extract_sample(SamiRegularStatusDataParticle, REGULAR_STATUS_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(SamiControlRecordDataParticle, CONTROL_RECORD_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(SamiErrorCodeDataParticle, ERROR_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(PhsenSamiSampleDataParticle, SAMI_SAMPLE_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(PhsenConfigDataParticle, CONFIGURATION_REGEX_MATCHER, chunk, timestamp)

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
