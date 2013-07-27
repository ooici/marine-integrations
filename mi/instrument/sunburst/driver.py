"""
@package mi.instrument.sunburst.driver
@file marine-integrations/mi/instrument/sunburst/driver.py
@author Stuart Pearce and Chris Wingard
@brief Base Driver for the SAMI instruments
Release notes:

Sunburst Sensors SAMI2-PH pH underwater sensor
"""

__author__ = 'Chris Wingard & Stuart Pearce'
__license__ = 'Apache 2.0'

import re
import datetime as dt

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException

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
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import FunctionParameter
from mi.core.instrument.driver_dict import DriverDictKey

# TODO: BASE CLASS
# newline.
NEWLINE = '\r'

# TODO: BASE CLASS
# default timeout.
TIMEOUT = 10

# TODO: BASE CLASS
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

# Error records
ERROR_REGEX = r'[?]([0-9A-Fa-f]{2})' + NEWLINE
ERROR_REGEX_MATCHER = re.compile(ERROR_REGEX)


###
#    Begin Classes
###
# TODO: BASE CLASS and will require inherit extend
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
    WAITING = 'PROTOCOL_STATE_WAITING'
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    SCHEDULED_SAMPLE = 'PROTOCOL_STATE_SCHEDULED_SAMPLE'
    POLLED_SAMPLE = 'PROTOCOL_STATE_POLLED_SAMPLE'


class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    #ACQUIRE_CONFIGURATION = 'DRIVER_EVENT_ACQUIRE_CONFIGURATION'
    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    ACQUIRE_STATUS = DriverEvent.ACQUIRE_STATUS

    # New Protocol Events as discussed with Bill F. regarding a SUCCESS and a
    # TIMEOUT event for the SCHEDULED_SAMPLE and POLLED_SAMPLE states.
    SUCCESS = 'PROTOCOL_EVENT_SUCCESS'
    TIMEOUT = 'PROTOCOL_EVENT_TIMEOUT'


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    # ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE  # why not ACQUIRE_SAMPLE ?
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
    START_DIRECT = ProtocolEvent.START_DIRECT
    STOP_DIRECT = ProtocolEvent.STOP_DIRECT


class SamiParameter(DriverParameter):
    """
    Base SAMI specific parameters.  Extend these with device specific
    parameters in a subclass named Parameter.
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
    # make sure to extend these in the individual drivers with the
    # the portions of the configuration that is unique to each.


# TODO: talk to Chris about prompts.
class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """
    BOOT_PROMPT = '7.7Boot>'


# TODO: BASE CLASS with inherit extend (R1 and Blank only difference?)
class SamiInstrumentCommand(BaseEnum):
    """
    Base SAMI Instrument command strings.  Extend these with device specific
    commands in a subclass named InstrumentCommand.

    This particularly applies to the PCO2 where an additional ACQUIRE_SAMPLE
    command is required for device 1, the external pump.
    """
    GET_STATUS = 'S0'
    START_STATUS = 'F0'
    STOP_STATUS = 'F5A'
    GET_CONFIG = 'L'
    SET_CONFIG = 'L5A'
    ERASE_ALL = 'E5A'
    START = 'G5A'
    STOP = 'Q5A'
    ACQUIRE_SAMPLE_SAMI = 'R0'
    ESCAPE_BOOT = 'u'
    #ACQUIRE_SAMPLE_DEV1 = 'R1'  # Extend in indv. driver?
    # TODO: Ask Chris if you have to give a command for a blank sample


###############################################################################
# Data Particles
###############################################################################


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
        grp_index = 1
        for key in particle_keys:
            result.append({DataParticleKey.VALUE_ID: key,
                           DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
            grp_index += 1

        return result


class SamiConfigDataParticleKey(BaseEnum):
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
    # make sure to extend these in the individual drivers with the
    # the portions of the configuration that is unique to each.


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
        self._protocol_fsm = InstrumentFSM(
            ProtocolState, ProtocolEvent,
            ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine
        self._protocol_fsm.add_handler(
            ProtocolState.UNKNOWN, ProtocolEvent.ENTER,
            self._handler_unknown_enter)
        self._protocol_fsm.add_handler(
            ProtocolState.UNKNOWN, ProtocolEvent.EXIT,
            self._handler_unknown_exit)
        self._protocol_fsm.add_handler(
            ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER,
            self._handler_unknown_discover)
        self._protocol_fsm.add_handler(
            ProtocolState.UNKNOWN, ProtocolEvent.START_DIRECT,
            self._handler_command_start_direct)

        self._protocol_fsm.add_handler(
            ProtocolState.WAITING, ProtocolEvent.ENTER,
            self._handler_waiting_enter)
        self._protocol_fsm.add_handler(
            ProtocolState.WAITING, ProtocolEvent.EXIT,
            self._handler_waiting_exit)
        self._protocol_fsm.add_handler(
            ProtocolState.WAITING, ProtocolEvent.DISCOVER,
            self._handler_waiting_discover)

        self._protocol_fsm.add_handler(
            ProtocolState.COMMAND, ProtocolEvent.ENTER,
            self._handler_command_enter)
        self._protocol_fsm.add_handler(
            ProtocolState.COMMAND, ProtocolEvent.EXIT,
            self._handler_command_exit)
        self._protocol_fsm.add_handler(
            ProtocolState.COMMAND, ProtocolEvent.GET,
            self._handler_command_get)
        self._protocol_fsm.add_handler(
            ProtocolState.COMMAND, ProtocolEvent.SET,
            self._handler_command_set)
        self._protocol_fsm.add_handler(
            ProtocolState.COMMAND, ProtocolEvent.START_DIRECT,
            self._handler_command_start_direct)
        self._protocol_fsm.add_handler(
            ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS,
            self._handler_command_acquire_status)
        self._protocol_fsm.add_handler(
            ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE,
            self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(
            ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE,
            self._handler_command_start_autosample)
        # the ACQUIRE_CONFIGURATION event may not be necessary
        #self._protocol_fsm.add_handler(
        #    ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_CONFIGURATION,
        #    self._handler_command_acquire_configuration)

        self._protocol_fsm.add_handler(
            ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER,
            self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(
            ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT,
            self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(
            ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT,
            self._handler_direct_access_stop_direct)
        self._protocol_fsm.add_handler(
            ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT,
            self._handler_direct_access_execute_direct)

        self._protocol_fsm.add_handler(
            ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER,
            self._handler_autosample_enter)
        self._protocol_fsm.add_handler(
            ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT,
            self._handler_autosample_exit)
        self._protocol_fsm.add_handler(
            ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE,
            self._handler_autosample_stop)
        self._protocol_fsm.add_handler(
            ProtocolState.AUTOSAMPLE, ProtocolEvent.ACQUIRE_SAMPLE,
            self._handler_autosample_acquire_sample)

        # this state would be entered whenever an ACQUIRE_SAMPLE event occurred
        # while in the AUTOSAMPLE state and will last anywhere from 10 seconds
        # to 3 minutes depending on instrument and the type of sampling.
        self._protocol_fsm.add_handler(
            ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.ENTER,
            self._handler_scheduled_sample_enter)
        self._protocol_fsm.add_handler(
            ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.EXIT,
            self._handler_scheduled_sample_exit)

        # this state would be entered whenever an ACQUIRE_SAMPLE event occurred
        # while in either the COMMAND state (or via the discover transition
        # from the UNKNOWN state with the instrument unresponsive) and will
        # last anywhere from a few seconds to 3 minutes depending on instrument
        # and sample type.
        self._protocol_fsm.add_handler(
            ProtocolState.POLLED_SAMPLE, ProtocolEvent.ENTER,
            self._handler_polled_sample_enter)
        self._protocol_fsm.add_handler(
            ProtocolState.POLLED_SAMPLE, ProtocolEvent.EXIT,
            self._handler_polled_sample_exit)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCommand.GET_STATUS, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.START_STATUS, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.STOP_STATUS, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.GET_CONFIG, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.SET_CONFIG, self._build_set_config)
        self._add_build_handler(InstrumentCommand.ERASE_ALL, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.START, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.STOP, self._build_simple_command)
        self._add_build_handler(InstrumentCommand.ACQUIRE_SAMPLE_SAMI, self._build_sample_sami)
        self._add_build_handler(InstrumentCommand.ESCAPE_BOOT, self._build_escape_boot)
        # Add this statement in the Protocol.__init__ method in the Pco2 driver
        #self._add_build_handler(InstrumentCommand.ACQUIRE_SAMPLE_DEV1, self._build_sample_dev1)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCommand.GET_STATUS, self._build_response_get_status)
        self._add_response_handler(InstrumentCommand.GET_CONFIG, self._build_response_get_config)
        self._add_response_handler(InstrumentCommand.SET_CONFIG, self._build_response_set_config)
        self._add_response_handler(InstrumentCommand.ERASE_ALL, self._build_response_erase_all)
        self._add_response_handler(InstrumentCommand.ACQUIRE_SAMPLE_SAMI, self._build_response_sample_sami)
        # Add this statement in the Protocol.__init__ method in the Pco2 driver
        #self._add_response_handler(InstrumentCommand.ACQUIRE_SAMPLE_DEV1, self._build_response_sample_dev1)

        # Add sample handlers.

        # Start state machine in UNKNOWN state.
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

        # Put this list into the indv. drivers as a constant
        # SIEVE_MATCHERS = [REGULAR_STATUS_REGEX_MATCHER,
        #                  CONTROL_RECORD_REGEX_MATCHER,
        #                  SAMI_SAMPLE_REGEX_MATCHER,
        #                  CONFIGURATION_REGEX_MATCHER,
        #                  ERROR_REGEX_MATCHER]

        for matcher in SIEVE_MATCHERS:
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
        self._extract_sample(PhsenSamiSampleDataParticle, SAMI_SAMPLE_REGEX_MATCHER, chunk, timestamp)
        self._extract_sample(PhsenConfigDataParticle, CONFIGURATION_REGEX_MATCHER, chunk, timestamp)
        # Probably not needed
        #self._extract_sample(SamiErrorCodeDataParticle, ERROR_REGEX_MATCHER, chunk, timestamp)

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
        # Turn on debugging
        log.debug("_handler_unknown_enter")

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
        Discover current state; can be UNKNOWN, COMMAND or POLLED_SAMPLE
        @retval (next_state, result)
        """
        next_state = None
        result = None

        log.debug("_handler_unknown_discover: starting discover")
        (next_state, next_agent_state) = self._discover()
        log.debug("_handler_unknown_discover: next agent state: %s", next_agent_state)

        return (next_state, (next_agent_state, result))

    ########################################################################
    # Waiting handlers.
    ########################################################################

    def _handler_waiting_enter(self, *args, **kwargs):
        """
        Enter discover state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        # Test to determine what state we truly are in, command or unknown.
        self._protocol_fsm.on_event(ProtocolEvent.DISCOVER)

    def _handler_waiting_exit(self, *args, **kwargs):
        """
        Exit discover state.
        """
        pass

    def _handler_waiting_discover(self, *args, **kwargs):
        """
        Discover current state; can be UNKNOWN or COMMAND
        @retval (next_state, result)
        """
        # Exit states can be either COMMAND or back to UNKNOWN.
        next_state = None
        next_agent_state = None
        result = None

        # try to discover our state
        count = 1
        while count <= 6:
            log.debug("_handler_waiting_discover: starting discover")
            (next_state, next_agent_state) = self._discover()
            if next_state is ProtocolState.COMMAND:
                log.debug("_handler_waiting_discover: discover succeeded")
                log.debug("_handler_waiting_discover: next agent state: %s", next_agent_state)
                return (next_state, (next_agent_state, result))
            else:
                log.debug("_handler_waiting_discover: discover failed, attempt %d of 3", count)
                count += 1
                time.sleep(20)

        log.debug("_handler_waiting_discover: discover failed")
        log.debug("_handler_waiting_discover: next agent state: %s", ResourceAgentState.ACTIVE_UNKNOWN)
        return (ProtocolState.UNKNOWN, (ResourceAgentState.ACTIVE_UNKNOWN, result))

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

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

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

    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        result = None
        log.debug("_handler_command_start_direct: entering DA mode")
        return (next_state, (next_agent_state, result))

    def _handler_command_acquire_configuration(self, *args, **kwargs):
        """
        Acquire the instrument's configuration
        """
        next_state = None
        result = None

        return (next_state, result)

    def _handler_command_acquire_status(self, *args, **kwargs):
        """
        Acquire the instrument's status
        """
        next_state = None
        result = None

        return (next_state, result)

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire a sample
        """
        next_state = None
        result = None

        return (next_state, result)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Start autosample mode (spoofed via use of scheduler)
        """
        next_state = None
        result = None

        return (next_state, result)

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

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, ):
        """
        Enter Autosample state
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state
        """
        pass

    def _handler_autosample_stop(self, *args, **kwargs):
        """
        Stop autosample
        """
        next_state = None
        result = None

        return (next_state, result)

    def _handler_autosample_acquire_sample(self, *args, **kwargs):
        """
        While in autosample mode, poll for samples using the scheduler
        """
        next_state = None
        result = None

        return (next_state, result)

    ########################################################################
    # Scheduled Sample handlers.
    ########################################################################

    def _handler_scheduled_sample_enter(self, *args, **kwargs):
        """
        Enter busy state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_scheduled_sample_exit(self, *args, **kwargs):
        """
        Exit busy state.
        """
        pass

    ########################################################################
    # Polled Sample handlers.
    ########################################################################

    def _handler_polled_sample_enter(self, *args, **kwargs):
        """
        Enter busy state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_polled_sample_exit(self, *args, **kwargs):
        """
        Exit busy state.
        """
        pass

    ####################################################################
    # Build Command & Parameter dictionary
    ####################################################################

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """
        self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name="acquire status")
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="start autosample")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="stop autosample")
        self._cmd_dict.add(Capability.START_DIRECT, display_name="start direct access")
        self._cmd_dict.add(Capability.STOP_DIRECT, display_name="stop direct access")

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """
        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        self._param_dict = ProtocolParameterDict()

        ### example configuration string
        #VALID_CONFIG_STRING = 'CDDD731D01E1338001E1338002000E100A0200000000110' + \
        #'0000000110000000011000000001107013704200108081004081008170000' + \
        #'0000000000000000000000000000000000000000000000000000000000000' + \
        #'0000000000000000000000000000000000000000000000000000000000000' + \
        #'00' + \
        #'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
        #'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + NEWLINE

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

    @staticmethod
    def _int_to_hexstring(self, val, slen):
        """
        Write an integer value to an ASCIIHEX string formatted for SAMI
        configuration set operations.
        @param v the integer value to convert.
        @param slen the required length of the returned string.
        @retval an integer string formatted in ASCIIHEX for SAMI configuration
        set operations.
        @throws InstrumentParameterException if the integer and string length
        values are not an integers.
        """
        if not isinstance(val, int):
            raise InstrumentParameterException('Value %s is not an integer.' % str(val))
        elif not isinstance(slen, int):
            raise InstrumentParameterException('Value %s is not an integer.' % str(slen))
        else:
            s = format(val, 'X')
            return s.zfill(slen)
