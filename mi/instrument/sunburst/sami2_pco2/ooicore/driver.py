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
    REGULAR_STATUS = 'regular_status'
    CONTROL_RECORD = 'control_record'
    SAMI_SAMPLE = 'sami_sample'
    DEV1_SAMPLE = 'dev1_sample'
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
                       '([0-9A-Fa-f]{6})([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})' + NEWLINE
REGULAR_STATUS_REGEX_MATCHER = re.compile(REGULAR_STATUS_REGEX)

# Control Records (Types 0x80 - 0xFF)
CONTROL_RECORD_REGEX = r'[\*]([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([8-9A-Fa-f][0-9A-Fa-f])' + \
                       '([0-9A-Fa-f]{8})([0-9A-Fa-f]{4})([0-9A-Fa-f]{6})' + \
                       '([0-9A-Fa-f]{6})([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})' + NEWLINE
CONTROL_RECORD_REGEX_MATCHER = re.compile(CONTROL_RECORD_REGEX)

# SAMI Sample Records (Types 0x04 or 0x05)
SAMI_SAMPLE_REGEX = r'[\*]([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})(04|05)' + \
                    '([0-9A-Fa-f]{8})([0-9A-Fa-f]{56})([0-9A-Fa-f]{4})' + \
                    '([0-9A-Fa-f]{4})([0-9A-Fa-f]{2})' + NEWLINE
SAMI_SAMPLE_REGEX_MATCHER = re.compile(SAMI_SAMPLE_REGEX)

# Device 1 Sample Records (Type 0x11)
DEV1_SAMPLE_REGEX = r'[\*]([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})(11)([0-9A-Fa-f]{8})([0-9A-Fa-f]{2})' + NEWLINE
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
                      '([0-9A-Fa-f]+)' + NEWLINE
CONFIGURATION_REGEX_MATCHER = re.compile(CONFIGURATION_REGEX)

# Error records
ERROR_REGEX = r'[?]([0-9A-Fa-f]{2})' + NEWLINE
ERROR_REGEX_MATCHER = re.compile(ERROR_REGEX)


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
    FLASH_ERASED = 'FLASH_ERASED'
    POWER_ON_INVALID = 'power_on_invalid'
    NUM_DATA_RECORDS = 'num_data_records'
    NUM_ERROR_RECORDS = 'num_error_records'
    NUM_BYTES_STORED = 'num_bytes_stored'
    CHECKSUM = 'checksum'


# [TODO: This needs to be moved to the baseclass]
class SamiRegularStatusDataParticle(DataParticle):
    """
    Routines for parsing raw data into an regular status data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """
    _data_particle_type = DataParticleType.REGULAR_STATUS

    def _build_parsed_values(self):
        """
        Parse air sample values from raw data into a dictionary
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
        bit_index = 0

        for key in particle_keys:
            if key in [SamiRegularStatusDataParticleKey.ELAPSED_TIME_CONFIG]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(1), 16)})
            elif key in [SamiRegularStatusDataParticleKey.CLOCK_ACTIVE,
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
            else:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(3), 16)})

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
    FLASH_ERASED = 'FLASH_ERASED'
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
            if key in [SamiControlRecordDataParticleKey.UNIQUE_ID,
                       SamiControlRecordDataParticleKey.RECORD_LENGTH,
                       SamiControlRecordDataParticleKey.RECORD_TYPE,
                       SamiControlRecordDataParticleKey.RECORD_TIME]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
            elif key in [SamiControlRecordDataParticleKey.CLOCK_ACTIVE,
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
            else:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})

            grp_index += 1

        return result


class SamiErrorCodeDataParticleKey(BaseEnum):
    """
    Data particle key for the error code records.
    """
    ERROR_CODE = 'error_code'


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
        for key in particle_keys:
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: int(matched.group(key+1), 16)})

        return result


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
    _data_particle_type = DataParticleType.SAMI_SAMPLE

    def _build_parsed_values(self):
        """
        Parse SAMI2-PCO2 values from raw data into a dictionary
        """

        matched = SAMI_SAMPLE_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [Pco2wSamiSampleDataParticleKey.UNIQUE_ID,
                         Pco2wSamiSampleDataParticleKey.RECORD_LENGTH,
                         Pco2wSamiSampleDataParticleKey.RECORD_TYPE,
                         Pco2wSamiSampleDataParticleKey.RECORD_TIME,
                         Pco2wSamiSampleDataParticleKey.LIGHT_MEASUREMENTS,
                         Pco2wSamiSampleDataParticleKey.VOLTAGE_BATTER,
                         Pco2wSamiSampleDataParticleKey.THERMISTER_RAW,
                         Pco2wSamiSampleDataParticleKey.CHECKSUM]

        result = []
        for key in particle_keys:
            if key in [Pco2wSamiSampleDataParticleKey.LIGHT_MEASUREMENTS]:
                # parse group 5 into 14, 2 byte (4 character) values stored in
                # an array.
                light = matched.group(key+1)
                light = [int(light[i:i+4], 16) for i in range(0, len(light), 4)]
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: light})
            else:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})

        return result


class Pco2wDev1SampleDataParticleKey(BaseEnum):
    """
    Data particle key for the device 1 (external pump) records. These particles
    capture when a sample was collected.
    """
    UNIQUE_ID = 'unique_id'
    RECORD_LENGTH = 'record_length'
    RECORD_TYPE = 'record_type'
    RECORD_TIME = 'record_time'
    CHECKSUM = 'checksum'


class Pco2wDev1SampleDataParticle(DataParticle):
    """
    Routines for parsing raw data into a device 1 sample data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """
    _data_particle_type = DataParticleType.DEV1_SAMPLE

    def _build_parsed_values(self):
        """
        Parse device 1 values from raw data into a dictionary
        """

        matched = DEV1_SAMPLE_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        particle_keys = [Pco2wDev1SampleDataParticleKey.UNIQUE_ID,
                         Pco2wDev1SampleDataParticleKey.RECORD_LENGTH,
                         Pco2wDev1SampleDataParticleKey.RECORD_TYPE,
                         Pco2wDev1SampleDataParticleKey.RECORD_TIME,
                         Pco2wDev1SampleDataParticleKey.CHECKSUM]

        result = []
        for key in particle_keys:
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: int(matched.group(key+1), 16)})

        return result


class Pco2wConfigurationDataParticleKey(BaseEnum):
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
    PUMP_PULSE = 'pump_pulse'
    PUMP_ON_TO_MEAURSURE = 'pump_on_to_meaursure'
    SAMPLES_PER_MEASURE = 'samples_per_measure'
    CYCLES_BETWEEN_BLANKS = 'cycles_between_blanks'
    NUM_REAGENT_CYCLES = 'num_reagent_cycles'
    NUM_BLANK_CYCLES = 'num_blank_cycles'
    FLUSH_PUMP_INTERVAL = 'flush_pump_interval'
    DISABLE_START_BLANK_FLUSH = 'disable_start_blank_flush'
    MEASURE_AFTER_PUMP_PULSE = 'measure_after_pump_pulse'
    CYCLE_RATE = 'cycle_rate'
    EXTERNAL_PUMP_SETTING = 'external_pump_setting'


class Pco2wConfigurationDataParticle(DataParticle):
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

        particle_keys = [Pco2wConfigurationDataParticleKey.LAUNCH_TIME,
                         Pco2wConfigurationDataParticleKey.START_TIME_OFFSET,
                         Pco2wConfigurationDataParticleKey.RECORDING_TIME,
                         Pco2wConfigurationDataParticleKey.PMI_SAMPLE_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SAMI_SAMPLE_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE,
                         Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_SAMI,
                         Pco2wConfigurationDataParticleKey.DRIVER_ID_SAMI,
                         Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_SAMI,
                         Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE1,
                         Pco2wConfigurationDataParticleKey.DRIVER_ID_DEVICE1,
                         Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE1,
                         Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE2,
                         Pco2wConfigurationDataParticleKey.DRIVER_ID_DEVICE2,
                         Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE2,
                         Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE3,
                         Pco2wConfigurationDataParticleKey.DRIVER_ID_DEVICE3,
                         Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE3,
                         Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_PRESTART,
                         Pco2wConfigurationDataParticleKey.DRIVER_ID_PRESTART,
                         Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_PRESTART,
                         Pco2wConfigurationDataParticleKey.USE_BAUD_RATE_57600,
                         Pco2wConfigurationDataParticleKey.SEND_RECORD_TYPE,
                         Pco2wConfigurationDataParticleKey.SEND_LIVE_RECORDS,
                         Pco2wConfigurationDataParticleKey.EXTEND_GLOBAL_CONFIG,
                         Pco2wConfigurationDataParticleKey.PUMP_PULSE,
                         Pco2wConfigurationDataParticleKey.PUMP_ON_TO_MEAURSURE,
                         Pco2wConfigurationDataParticleKey.SAMPLES_PER_MEASURE,
                         Pco2wConfigurationDataParticleKey.CYCLES_BETWEEN_BLANKS,
                         Pco2wConfigurationDataParticleKey.NUM_REAGENT_CYCLES,
                         Pco2wConfigurationDataParticleKey.NUM_BLANK_CYCLES,
                         Pco2wConfigurationDataParticleKey.FLUSH_PUMP_INTERVAL,
                         Pco2wConfigurationDataParticleKey.DISABLE_START_BLANK_FLUSH,
                         Pco2wConfigurationDataParticleKey.MEASURE_AFTER_PUMP_PULSE,
                         Pco2wConfigurationDataParticleKey.CYCLE_RATE,
                         Pco2wConfigurationDataParticleKey.EXTERNAL_PUMP_SETTING]

        result = []
        grp_index = 1
        mode_index = 0
        glbl_index = 0
        sami_index = 0

        for key in particle_keys:
            if key in [Pco2wConfigurationDataParticleKey.PMI_SAMPLE_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SAMI_SAMPLE_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE,
                       Pco2wConfigurationDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(4), 16) & (1 << mode_index))})
                mode_index += 1

            elif key in [Pco2wConfigurationDataParticleKey.USE_BAUD_RATE_57600,
                         Pco2wConfigurationDataParticleKey.SEND_RECORD_TYPE,
                         Pco2wConfigurationDataParticleKey.SEND_LIVE_RECORDS,
                         Pco2wConfigurationDataParticleKey.EXTEND_GLOBAL_CONFIG]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(20), 16) & (1 << glbl_index))})
                glbl_index += 1
                if glbl_index == 3:
                    glbl_index = 7

            elif key in [Pco2wConfigurationDataParticleKey.DISABLE_START_BLANK_FLUSH,
                         Pco2wConfigurationDataParticleKey.MEASURE_AFTER_PUMP_PULSE]:
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(28), 16) & (1 << sami_index))})
                sami_index += 1

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
                          DEV1_SAMPLE_REGEX_MATCHER,
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
        The base class got_data has gotten a chunk from the chunker. Pass it to
        extract_sample with the appropriate particle objects and REGEXes.
        """
        self._extract_sample(SamiRegularStatusDataParticle, REGULAR_STATUS_REGEX_MATCHER, chunk, timestamp)

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
