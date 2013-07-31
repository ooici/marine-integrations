"""
@package mi.instrument.sunburst.driver
@file marine-integrations/mi/instrument/sunburst/driver.py
@author Stuart Pearce and Chris Wingard
@brief Base Driver for the SAMI instruments
Release notes:

Sunburst Instruments SAMI-PCO2 partial CO2 & SAMI2-PH pH underwater sensors
"""

__author__ = 'Chris Wingard & Stuart Pearce'
__license__ = 'Apache 2.0'

import re
import time

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException

from mi.core.common import BaseEnum
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.driver_dict import DriverDictKey
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
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
SAMI_TO_UNIX = 2082844800
# Conversion from SAMI time (seconds since 1904-01-01) to NTP timestamps
# (seconds since 1900-01-01). Subtract this value to convert NTP timestamps to
# SAMI, and add for the reverse.
SAMI_TO_NTP = 126144000

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
    r'[*]' +  # record identifier
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
class SamiDataParticleType(BaseEnum):
    """
    Base class Data particle types produced by a SAMI instrument. Should be
    sub-classed in the specific instrument driver
    """
    RAW = CommonDataParticleType.RAW
    REGULAR_STATUS = 'regular_status'
    CONTROL_RECORD = 'control_record'
    SAMI_SAMPLE = 'sami_sample'
    CONFIGURATION = 'configuration'


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
    ACQUIRE_CONFIGURATION = 'DRIVER_EVENT_ACQUIRE_CONFIGURATION'
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
    # ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE  # why not ACQUIRE_SAMPLE?
    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    START_DIRECT = ProtocolEvent.START_DIRECT
    STOP_DIRECT = ProtocolEvent.STOP_DIRECT


class SamiParameter(DriverParameter):
    """
    Base SAMI instrument parameters. Subclass and extend this Enum with device
    specific parameters in subclass 'Parameter'.
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


# TODO: Find out about use of prompts
class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """
    BOOT_PROMPT = '7.7Boot>'


class SamiInstrumentCommand(BaseEnum):
    """
    Base SAMI instrument command strings. Subclass and extend these with device
    specific commands in subclass 'InstrumentCommand'.

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
    _data_particle_type = SamiDataParticleType.REGULAR_STATUS

    def _build_parsed_values(self):
        """
        Parse regular status values from raw data into a dictionary
        """

        ### Regular Status Messages
        # Produced in response to S0 command, or automatically at 1 Hz. All
        # regular status messages are preceeded by the ':' character and
        # terminate with a '/r'. Sample string:
        #
        #   :CEE90B1B004100000100000000021254
        #
        # These messages consist of the time since the last configuration,
        # status flags, the number of data records, the number of error
        # records, the number of bytes stored (including configuration bytes),
        # and a checksum.
        ###

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
        grp_index = 1  # used to index through match groups, starting at 1
        bit_index = 0  # used to index through the bit fields represented by
                       # the two bytes after CLOCK_ACTIVE.

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
                # if the keys match values represented by the bits in the two
                # byte status flags value, parse bit-by-bit using the bit-shift
                # operator to determine the boolean value.
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(2), 16) & (1 << bit_index))})
                bit_index += 1  # bump the bit index
                grp_index = 3  # set the right group index for when we leave this part of the loop.
            else:
                # otherwise all values in the string are parsed to integers
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
    _data_particle_type = SamiDataParticleType.CONTROL_RECORD

    def _build_parsed_values(self):
        """
        Parse control record values from raw data into a dictionary
        """

        ### Control Records
        # Produced by the instrument periodically in reponse to certain events
        # (e.g. when the Flash memory is opened). The messages are preceded by
        # a '*' character and terminated with a '\r'. Sample string:
        #
        #   *541280CEE90B170041000001000000000200AF
        #
        # A full description of the control record strings can be found in the
        # vendor supplied SAMI Record Format document.
        ###

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
        grp_index = 1  # used to index through match groups, starting at 1
        bit_index = 0  # used to index through the bit fields represented by
                       # the two bytes after CLOCK_ACTIVE.

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
                # if the keys match values represented by the bits in the two
                # byte status flags value included in all control records,
                # parse bit-by-bit using the bit-shift operator to determine
                # boolean value.
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: bool(int(matched.group(5), 16) & (1 << bit_index))})
                bit_index += 1  # bump the bit index
                grp_index = 6  # set the right group index for when we leave this part of the loop.
            else:
                # otherwise all values in the string are parsed to integers
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: int(matched.group(grp_index), 16)})
                grp_index += 1

        return result


class SamiConfigDataParticleKey(BaseEnum):
    """
    SAMI Instrument Data particle key Base Class for configuration records.
    This should be subclassed in the specific instrument driver and extended
    with specific instrument parameters.
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

class SamiInstrumentDriver(SingleConnectionInstrumentDriver):
    """
    SamiInstrumentDriver baseclass
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.

    Needs to be subclassed again in the specific driver module to call Protocol
    in the _build_protocol method correctly
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

    #########################################################################
    ## Protocol builder.  create this definition in the subclassed driver
    #########################################################################
    #
    #def _build_protocol(self):
    #    """
    #    Construct the driver protocol state machine.
    #    """
    #    self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

class SamiProtocol(CommandResponseInstrumentProtocol):
    """
    SAMI Instrument protocol class
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
        # TODO: these next two may need to be added at the specific driver
        # level or at least the handlers
        #self._protocol_fsm.add_handler(
        #    ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.SUCCESS,
        #    self._handler_sample_success)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.TIMEOUT,
        #    self._handler_sample_timeout)

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
        # TODO: these next two may need to be added at the specific driver
        # level, or at least the handlers
        #self._protocol_fsm.add_handler(
        #    ProtocolState.POLLED_SAMPLE, ProtocolEvent.SUCCESS,
        #    self._handler_sample_success)
        #self._protocol_fsm.add_handler(
        #    ProtocolState.POLLED_SAMPLE, ProtocolEvent.TIMEOUT,
        #    self._handler_sample_timeout)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        # Add build handlers for device commands.
        self._add_build_handler(SamiInstrumentCommand.GET_STATUS, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.START_STATUS, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.STOP_STATUS, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.GET_CONFIG, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.SET_CONFIG, self._build_set_config)
        self._add_build_handler(SamiInstrumentCommand.ERASE_ALL, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.START, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.STOP, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.ACQUIRE_SAMPLE_SAMI, self._build_sample_sami)
        self._add_build_handler(SamiInstrumentCommand.ESCAPE_BOOT, self._build_escape_boot)
        # Add this statement in the Protocol.__init__ method in the Pco2 driver
        #self._add_build_handler(InstrumentCommand.ACQUIRE_SAMPLE_DEV1, self._build_sample_dev1)

        # Add response handlers for device commands.
        self._add_response_handler(SamiInstrumentCommand.GET_STATUS, self._build_response_get_status)
        self._add_response_handler(SamiInstrumentCommand.GET_CONFIG, self._build_response_get_config)
        self._add_response_handler(SamiInstrumentCommand.SET_CONFIG, self._build_response_set_config)
        self._add_response_handler(SamiInstrumentCommand.ERASE_ALL, self._build_response_erase_all)
        self._add_response_handler(SamiInstrumentCommand.ACQUIRE_SAMPLE_SAMI, self._build_response_sample_sami)
        # Add this statement in the Protocol.__init__ method in the Pco2 driver
        #self._add_response_handler(InstrumentCommand.ACQUIRE_SAMPLE_DEV1, self._build_response_sample_dev1)

        # Add sample handlers.

        # NOTE: I think this needs to be started in the subclass since more handlers will be added.
        ## Start state machine in UNKNOWN state.
        #self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        # Goes in the sub driver
        #self._chunker = StringChunker(Protocol.sieve_function)

    # needs to be in the sub driver
    #@staticmethod
    #def sieve_function(raw_data):
    #    """
    #    The method that splits samples
    #    """
    #
    #    return_list = []
    #
    #    # This may not work !!!
    #    # SIEVE_MATCHERS = [REGULAR_STATUS_REGEX_MATCHER,
    #    #                  CONTROL_RECORD_REGEX_MATCHER,
    #    #                  SAMI_SAMPLE_REGEX_MATCHER,
    #    #                  CONFIGURATION_REGEX_MATCHER,
    #    #                  ERROR_REGEX_MATCHER]
    #
    #    for matcher in self.sieve_matchers:
    #        for match in matcher.finditer(raw_data):
    #            return_list.append((match.start(), match.end()))
    #
    #    return return_list

    # this should probably go into the specific driver
    #def _got_chunk(self, chunk, timestamp):
    #    """
    #    The base class got_data has gotten a chunk from the chunker.  Pass it to extract_sample
    #    with the appropriate particle objects and REGEXes.
    #    """
    #    self._extract_sample(SamiRegularStatusDataParticle, REGULAR_STATUS_REGEX_MATCHER, chunk, timestamp)
    #    self._extract_sample(SamiControlRecordDataParticle, CONTROL_RECORD_REGEX_MATCHER, chunk, timestamp)
    #    self._extract_sample(PhsenSamiSampleDataParticle, SAMI_SAMPLE_REGEX_MATCHER, chunk, timestamp)
    #    self._extract_sample(PhsenConfigDataParticle, CONFIGURATION_REGEX_MATCHER, chunk, timestamp)

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

        # Command device to initialize parameters and send a config change event.
        self._protocol_fsm.on_event(DriverEvent.INIT_PARAMS)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_init_params(self, *args, **kwargs):
        """
        initialize parameters
        """
        next_state = None
        result = None

        self._init_params()
        return (next_state, result)

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

    # Not used currently.  Maybe added later
    #def _handler_command_acquire_configuration(self, *args, **kwargs):
    #    """
    #    Acquire the instrument's configuration
    #    """
    #    next_state = None
    #    result = None
    #
    #    return (next_state, result)

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

    def _handler_command_start_autosample(self):
        """
        Start autosample mode (spoofed via use of scheduler)
        """
        next_state = ProtocolState.START_AUTOSAMPLE
        next_agent_state = ResourceAgentState.START_AUTOSAMPLE
        result = None
        log.debug("_handler_command_start_autosample: entering Autosample mode")
        return (next_state, (next_agent_state, result))

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

        # This commented out section is the old action taken
        #next_state = ProtocolState.COMMAND
        #next_agent_state = ResourceAgentState.COMMAND

        log.debug("_handler_direct_access_stop_direct: starting discover")
        (next_state, next_agent_state) = self._discover()
        log.debug("_handler_direct_access_stop_direct: next agent state: %s", next_agent_state)

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

    # NOTE:  I think that these handlers will be exactly the same and so can be
    # reduced to a single _handler_sample_[EVENT]
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

    # define in the instrument specific driver Protocol subclass these handlers
    # _handler_scheduled_sample_success & _handler_scheduled_sample_timeout

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

    # define in the instrument specific driver Protocol subclass these handlers
    # _handler_polled_sample_success & _handler_polled_sample_timeout

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

    # I think this will need to be created in the specific driver sub-class
    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
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
        # Extend any further _param_dict.add's in the specific driver subclass

        self._build_param_dict_contd()

    def _build_param_dict_contd(self):
        """
        This method should be overloaded in the specific driver submodule
        """
        pass

    ########################################################################
    # Command handlers.
    ########################################################################

    def _build_simple_command(self, cmd):
        """
        Build handler for basic SAMI commands.
        @param cmd the simple SAMI command to format.
        @retval The command to be sent to the device.
        """
        return cmd + NEWLINE

    def _build_set_config(self):
        pass

    def _build_sample_sami(self):
        pass

    def _build_escape_boot(self):
        pass

    # this needs to be defined in the subclass in the PCO2 specific driver
    #def _build_sample_dev1(self):
    #    pass

    ########################################################################
    # Response handlers.
    ########################################################################

    def _build_response_get_status(self):
        pass

    def _build_response_get_config(self):
        pass

    def _build_response_set_config(self):
        pass

    def _build_response_erase_all(self):
        pass

    def _build_response_sample_sami(self):
        pass

    # this needs to be defined in the subclass in the PCO2 specific driver
    #def _build_response_sample_dev1(self):
    #    pass

    ########################################################################
    # Private helpers.
    ########################################################################

    @staticmethod
    def _discover(self):
        """
        Discover current state; can be UNKNOWN, COMMAND or DISCOVER
        @retval (next_state, result)
        """
        # Exit states can be either COMMAND, DISCOVER or back to UNKNOWN.
        next_state = None
        next_agent_state = None

        log.debug("_discover")

        # Set response timeout to 10 seconds. Should be immediate if
        # communications are enabled and the instrument is not sampling.
        # Otherwise, sampling can take up to ~3 minutes to complete. Partial
        # strings are output during that time period.
        kwargs['timeout'] = 10

        # Make sure automatic-status updates are off. This will stop the
        # broadcast of information while we are trying to get data.
        cmd = self._build_simple_command(InstrumentCommand.STOP_STATUS)
        self._do_cmd_direct(cmd)

        # Acquire the current instrument status
        status = self._do_cmd_resp(InstrumentCommand.GET_STATUS, *args, **kwargs)
        status_match = REGULAR_STATUS_REGEX_MATCHER.match(status)

        if status is None or not status_match:
            # No response received in the timeout period, or response that does
            # not match the status string format is received. In either case,
            # we assume the unit is sampling and transition to a new state,
            # WAITING, to confirm or deny.
            next_state = ProtocolState.WAITING
            next_agent_state = ResourceAgentState.BUSY
        else:
            # Unit is powered on and ready to accept commands, etc.
            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.IDLE

        log.debug("_discover. result start: %s" % next_state)
        return (next_state, next_agent_state)

    @staticmethod
    def _int_to_hexstring(self, val, slen):
        """
        Write an integer value to an ASCIIHEX string formatted for SAMI
        configuration set operations.
        @param val the integer value to convert.
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

    @staticmethod
    def _epoch_to_sami(self):
        """
        Create a timestamp in seconds using January 1, 1904 as the Epoch
        @retval an integer value representing the number of seconds since
            January 1, 1904.
        """
        return int(time.time()) + SAMI_EPOCH
