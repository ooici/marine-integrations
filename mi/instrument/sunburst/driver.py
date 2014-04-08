"""
@package mi.instrument.sunburst.driver
@file marine-integrations/mi/instrument/sunburst/driver.py
@author Stuart Pearce and Chris Wingard
@brief Base Driver for the SAMI instruments
Release notes:
    Sunburst Instruments SAMI2-PCO2 partial CO2 & SAMI2-PH pH underwater
    sensors.

    This is the base driver that contains common code for the SAMI2
    instruments SAMI2-PCO2 & SAMI2-PH since they have the same basic
    SAMI2 operating structure.

    Some of this code also derives from initial code developed by Chris
    Center
"""

__author__ = 'Chris Wingard, Stuart Pearce & Kevin Stiemke'
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

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import NotImplementedException
from mi.core.exceptions import SampleException

from mi.core.time import get_timestamp
from mi.core.time import get_timestamp_delayed

log.debug('herb: ' + 'import sunburst/driver.py')

###
#    Driver Constant Definitions
###
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
SAMI_TO_NTP =  126144000  ## TODO: Do we use NTP time for anything?

# Acceptable time difference as specified in the IOS
TIME_THRESHOLD = 1

# Length of configuration string with '0' padding
# used to calculate number of '0' padding
CONFIG_WITH_0_PADDING = 232

# Length of configuration string with 'f' padding
# used to calculate number of 'f' padding
CONFIG_WITH_0_AND_F_PADDING = 512

# Length of an entire configuration string minus the NEWLINE, TODO: not currently used
CONFIG_WITH_PADDING_AND_TERMINATOR = 514

# Terminator at the end of a configuration string
CONFIG_TERMINATOR = '00'

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
ERROR_REGEX = r'[\?]([0-9A-Fa-f]{2})' + NEWLINE
ERROR_REGEX_MATCHER = re.compile(ERROR_REGEX)

## These are returned immediately after SAMI sample commands
BLANK_SAMPLE_RETURN_REGEX = (r'\^05')
BLANK_SAMPLE_RETURN_REGEX_MATCHER = re.compile(BLANK_SAMPLE_RETURN_REGEX)
SAMPLE_RETURN_REGEX = (r'\^04')
SAMPLE_RETURN_REGEX_MATCHER = re.compile(SAMPLE_RETURN_REGEX)

# Currently used to handle unexpected responses
WILD_CARD_REGEX  = r'.*' + NEWLINE
WILD_CARD_REGEX_MATCHER = re.compile(WILD_CARD_REGEX)

NEW_LINE_REGEX = NEWLINE
NEW_LINE_REGEX_MATCHER = re.compile(NEW_LINE_REGEX)

###
#    Begin Classes
###
class SamiDataParticleType(BaseEnum):
    """
    Base class Data particle types produced by a SAMI instrument. Should be
    sub-classed in the specific instrument driver
    """

    log.debug('herb: ' + 'class SamiDataParticleType(BaseEnum)')

    RAW = CommonDataParticleType.RAW
    REGULAR_STATUS = 'regular_status'
    CONTROL_RECORD = 'control_record'
    SAMI_SAMPLE = 'sami_sample'
    CONFIGURATION = 'configuration'


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """

    log.debug('herb: ' + 'class ProtocolState(BaseEnum)')

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

    log.debug('herb: ' + 'class ProtocolEvent(BaseEnum)')

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
    SUCCESS = 'PROTOCOL_EVENT_SUCCESS'  # success getting a sample
    TIMEOUT = 'PROTOCOL_EVENT_TIMEOUT'  # timeout while getting a sample


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """

    log.debug('herb: ' + 'class Capability(BaseEnum)')

    ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    START_DIRECT = ProtocolEvent.START_DIRECT
    STOP_DIRECT = ProtocolEvent.STOP_DIRECT


class SamiParameter(DriverParameter):
    """
    Base SAMI instrument parameters. Subclass and extend this Enum with device
    specific parameters in subclass 'Parameter'.
    """

    log.debug('herb: ' + 'class SamiParameter(DriverParameter)')

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

# TODO: Prompt is an edge case which should never ever occur.  If prompt ever appears device should go back to
# TODO: discover state and reconfigure (if possible)
class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """

    log.debug('herb: ' + 'class Prompt(BaseEnum)')

    # The boot prompt is the prompt of the SAMI2's Lower Level operating
    # system. If this prompt is reached, it means the SAMI2 instrument
    # software has crashed and needs to be restarted with the command
    # 'u'. If this has occurred, the instrument has been reset and will
    # be in an unconfigured state.
    BOOT_PROMPT = '7.7Boot>'


class SamiInstrumentCommand(BaseEnum):
    """
    Base SAMI instrument command strings. Subclass and extend these with device
    specific commands in subclass 'InstrumentCommand'.

    This applies to the PCO2 where an additional ACQUIRE_SAMPLE
    command is required for device 1, the external pump.
    """

    log.debug('herb: ' + 'class SamiInstrumentCommand(BaseEnum)')

    GET_STATUS = 'S0'
    START_STATUS = 'F0'
    STOP_STATUS = 'F5A'
    GET_CONFIG = 'L'
    SET_CONFIG = 'L5A'
    ERASE_ALL = 'E5A'

    # TODO: Will not use if recording on instrument is not done
    START = 'G5A'
    STOP = 'Q5A'

    ACQUIRE_BLANK_SAMPLE_SAMI = 'C'
    ACQUIRE_SAMPLE_SAMI = 'R0'
    # TODO: See prompt comment above, this command should not be necessary if total reconfiguration
    ESCAPE_BOOT = 'u'

###############################################################################
# Data Particles
###############################################################################


class SamiRegularStatusDataParticleKey(BaseEnum):
    """
    Data particle key for the regular (1 Hz or polled) status messages.
    """

    log.debug('herb: ' + 'class SamiRegularStatusDataParticleKey(BaseEnum)')

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
    UNIQUE_ID = 'unique_id'


class SamiRegularStatusDataParticle(DataParticle):
    """
    Routines for parsing raw data into an regular status data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """

    log.debug('herb: ' + 'class SamiRegularStatusDataParticle(DataParticle)')

    _data_particle_type = SamiDataParticleType.REGULAR_STATUS

    def _build_parsed_values(self):
        """
        Parse regular status values from raw data into a dictionary
        """

        log.debug('herb: ' + 'SamiRegularStatusDataParticle._build_parsed_values(): BEGIN')

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
        # and the instrument's unique id.
        ###

        log.debug('herb: ' + 'SamiRegularStatusDataParticle._build_parsed_values(): MATCH BEGIN')

        matched = REGULAR_STATUS_REGEX_MATCHER.match(self.raw_data)
        if not matched:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.decoded_raw)

        log.debug('herb: ' + 'SamiRegularStatusDataParticle._build_parsed_values(): MATCH END')

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
                         SamiRegularStatusDataParticleKey.UNIQUE_ID]

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

        log.debug('herb: ' + 'SamiRegularStatusDataParticle._build_parsed_values(): END')

        return result

# TODO: Have not encountered any control records, remove?
class SamiControlRecordDataParticleKey(BaseEnum):
    """
    Data particle key for peridoically produced control records.
    """

    log.debug('herb: ' + 'class SamiControlRecordDataParticleKey(BaseEnum)')

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

# TODO: Have not encountered any control records, remove?
class SamiControlRecordDataParticle(DataParticle):
    """
    Routines for parsing raw data into a control record data particle
    structure.
    @throw SampleException If there is a problem with sample creation
    """

    log.debug('herb: ' + 'class SamiControlRecordDataParticle(DataParticle)')

    _data_particle_type = SamiDataParticleType.CONTROL_RECORD

    def _build_parsed_values(self):
        """
        Parse control record values from raw data into a dictionary
        """

        log.debug('herb: ' + 'SamiControlRecordDataParticle._build_parsed_values()')

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
        grp_index = 1  # used to index through match groups, starting at 1/
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

    log.debug('herb: ' + 'class SamiConfigDataParticleKey(BaseEnum)')

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

    Needs to be subclassed in the specific driver module.
    """

    log.debug('herb: ' + 'class SamiInstrumentDriver(SingleConnectionInstrumentDriver)')

    def __init__(self, evt_callback):
        """
        Driver constructor.
        @param evt_callback Driver process event callback.
        """

        log.debug('herb: ' + 'SamiInstrumentDriver.__init__()')

        #Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)


###########################################################################
# Protocol
###########################################################################

class SamiProtocol(CommandResponseInstrumentProtocol):
    """
    SAMI Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol

    Should be sub-classed in specific driver.
    """

    log.debug('herb: ' + 'class SamiProtocol(CommandResponseInstrumentProtocol)')

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """

        log.debug('herb: ' + 'SamiProtocol.__init__()')

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
        ## TODO: Don't think we will be doing any getting or setting?  Other than discovery.
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
        ## TODO: Is get configuration not required?
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

        # this state would be entered whenever an ACQUIRE_SAMPLE event
        # occurred while in the AUTOSAMPLE state and will last anywhere
        # from 10 seconds to 3 minutes depending on instrument and the
        # type of sampling.


        self._protocol_fsm.add_handler(
            ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.ENTER,
            self._handler_scheduled_sample_enter)
        self._protocol_fsm.add_handler(
            ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.EXIT,
            self._handler_scheduled_sample_exit)
        self._protocol_fsm.add_handler(
            ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.SUCCESS,
            self._handler_sample_success)
        self._protocol_fsm.add_handler(
            ProtocolState.SCHEDULED_SAMPLE, ProtocolEvent.TIMEOUT,
            self._handler_sample_timeout)

        # this state would be entered whenever an ACQUIRE_SAMPLE event
        # occurred while in either the COMMAND state
        # and will last anywhere from a few seconds to 3
        # minutes depending on instrument and sample type.
        self._protocol_fsm.add_handler(
            ProtocolState.POLLED_SAMPLE, ProtocolEvent.ENTER,
            self._handler_polled_sample_enter)
        self._protocol_fsm.add_handler(
            ProtocolState.POLLED_SAMPLE, ProtocolEvent.EXIT,
            self._handler_polled_sample_exit)
        self._protocol_fsm.add_handler(
            ProtocolState.POLLED_SAMPLE, ProtocolEvent.SUCCESS,
            self._handler_sample_success)
        self._protocol_fsm.add_handler(
            ProtocolState.POLLED_SAMPLE, ProtocolEvent.TIMEOUT,
            self._handler_sample_timeout)

        # Construct the parameter dictionary containing device
        # parameters, current parameter values, and set formatting
        # functions.
        self._build_param_dict()
        self._build_command_dict()
        self._build_driver_dict()

        # Add build handlers for device commands.
        self._add_build_handler(SamiInstrumentCommand.GET_STATUS, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.START_STATUS, self._build_simple_command)  # Never want to do this
        self._add_build_handler(SamiInstrumentCommand.STOP_STATUS, self._build_simple_command)

        ## TODO: Not sure if get and set are needed
        self._add_build_handler(SamiInstrumentCommand.GET_CONFIG, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.SET_CONFIG, self._build_simple_command)

        self._add_build_handler(SamiInstrumentCommand.ERASE_ALL, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.START, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.STOP, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.ACQUIRE_BLANK_SAMPLE_SAMI, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.ACQUIRE_SAMPLE_SAMI, self._build_simple_command)
        self._add_build_handler(SamiInstrumentCommand.ESCAPE_BOOT, self._build_escape_boot)

        # Add response handlers for device commands.
        self._add_response_handler(SamiInstrumentCommand.GET_STATUS, self._parse_response_get_status)
        self._add_response_handler(SamiInstrumentCommand.GET_CONFIG, self._parse_response_get_config)
        self._add_response_handler(SamiInstrumentCommand.SET_CONFIG, self._parse_response_set_config)
        self._add_response_handler(SamiInstrumentCommand.ERASE_ALL, self._parse_response_erase_all)
        self._add_response_handler(SamiInstrumentCommand.ACQUIRE_BLANK_SAMPLE_SAMI, self._parse_response_blank_sample_sami)
        self._add_response_handler(SamiInstrumentCommand.ACQUIRE_SAMPLE_SAMI, self._parse_response_sample_sami)

        # Add sample handlers.

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        # continue __init__ in the sub-class in the specific driver

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """

        log.debug('herb: ' + 'SamiProtocol._filter_capabilities()')

        return [x for x in events if Capability.has(x)]

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """

        log.debug('herb: ' + 'SamiProtocol._handler_unknown_enter()')

        # Turn on debugging
        log.debug("_handler_unknown_enter")

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """

        log.debug('herb: ' + 'SamiProtocol._handler_unknown_exit()')

        pass

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be UNKNOWN, COMMAND or POLLED_SAMPLE
        @retval (next_state, result)
        """

        log.debug('herb: ' + 'SamiProtocol._handler_unknown_discover()')

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

        log.debug('herb: ' + 'SamiProtocol._handler_waiting_enter()')

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        # Test to determine what state we truly are in, command or unknown.
        self._protocol_fsm.on_event(ProtocolEvent.DISCOVER)

    def _handler_waiting_exit(self, *args, **kwargs):
        """
        Exit discover state.
        """

        log.debug('herb: ' + 'SamiProtocol._handler_waiting_exit()')

        pass

    def _handler_waiting_discover(self, *args, **kwargs):
        """
        Discover current state; can be UNKNOWN or COMMAND
        @retval (next_state, result)
        """

        log.debug('herb: ' + 'SamiProtocol._handler_waiting_discover()')

        # Exit states can be either COMMAND or back to UNKNOWN.
        next_state = None
        next_agent_state = None
        result = None

## TODO: Make configurable?
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
                ## TODO: Make configurable or longer?  Function of the timeout values?
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

        log.debug('herb: ' + 'SamiProtocol._handler_command_enter()')

        # Command device to update parameters and send a config change event.
        #self._update_params()
## TODO:
        # Command device to initialize parameters and send a config change event.
        # self._protocol_fsm.on_event(DriverEvent.INIT_PARAMS)

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_init_params(self, *args, **kwargs):
        """
        initialize parameters
        """

        log.debug('herb: ' + 'SamiProtocol._handler_command_init_params()')

        next_state = None
        result = None

        self._init_params()
        return (next_state, result)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """

        log.debug('herb: ' + 'SamiProtocol._handler_command_exit()')

        pass

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """

        log.debug('herb: ' + 'SamiProtocol._handler_command_get()')

        next_state = None
        result = None

        return (next_state, result)

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """

        log.debug('herb: ' + 'SamiProtocol._handler_command_set()')

        next_state = None
        result = None

        return (next_state, result)

    def _handler_command_start_direct(self):
        """
        Start direct access
        """

        log.debug('herb: ' + 'SamiProtocol._handler_command_start_direct()')

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

        log.debug('herb: ' + 'SamiProtocol._handler_command_acquire_status()')

        next_state = None
        result = None

        return (next_state, result)

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire a sample
        """

        log.debug('herb: ' + 'SamiProtocol._handler_command_acquire_sample()')

        next_state = None
        result = None

        return (next_state, result)

    def _handler_command_start_autosample(self):
        """
        Start autosample mode (spoofed via use of scheduler)
        """

        log.debug('herb: ' + 'SamiProtocol._handler_command_start_autosample()')

        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING  ## TODO: Not sure?
        result = None
        log.debug("_handler_command_start_autosample: entering Autosample mode")

        ## return (next_state, (next_agent_state, result))
        ## return (next_state, next_agent_state)
        ## return (next_state, result)

    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """

        log.debug('herb: ' + 'SamiProtocol._handler_direct_access_enter')

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """

        log.debug('herb: ' + 'SamiProtocol._handler_direct_access_exit')

        pass

    def _handler_direct_access_execute_direct(self, data):
        """
        """

        log.debug('herb: ' + 'SamiProtocol._handler_direct_access_execute_direct')

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

        log.debug('herb: ' + 'SamiProtocol._handler_direct_access_stop_direct')

        next_state = None
        result = None

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

        log.debug('herb: ' + 'SamiProtocol._handler_autosample_enter')

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state
        """

        log.debug('herb: ' + 'SamiProtocol._handler_autosample_exit')

        pass

    def _handler_autosample_stop(self, *args, **kwargs):
        """
        Stop autosample
        """

        log.debug('herb: ' + 'SamiProtocol._handler_autosample_stop')

        next_state = None
        result = None

        return (next_state, result)

    def _handler_autosample_acquire_sample(self, *args, **kwargs):
        """
        While in autosample mode, poll for samples using the scheduler
        """

        log.debug('herb: ' + 'SamiProtocol._handler_autosample_acquire_sample')

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

        log.debug('herb: ' + 'SamiProtocol._handler_scheduled_sample_enter')

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_scheduled_sample_exit(self, *args, **kwargs):
        """
        Exit busy state.
        """

        log.debug('herb: ' + 'SamiProtocol._handler_scheduled_sample_exit')

        pass

    ########################################################################
    # Polled Sample handlers.
    ########################################################################

    def _handler_polled_sample_enter(self, *args, **kwargs):
        """
        Enter busy state.
        """

        log.debug('herb: ' + 'SamiProtocol._handler_polled_sample_enter')

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_polled_sample_exit(self, *args, **kwargs):
        """
        Exit busy state.
        """

        log.debug('herb: ' + 'SamiProtocol._handler_polled_sample_exit')

        pass

    # handlers for the SUCCESS and TIMEOUT events associated with the
    # Polled Sample and Scheduled Sample states are defined in the sub
    # class.

    ####################################################################
    # Build Command & Parameter dictionary
    ####################################################################

    def _build_command_dict(self):
        """
        Populate the command dictionary with command.
        """

        log.debug('herb: ' + 'SamiProtocol._build_command_dict')

        self._cmd_dict.add(Capability.ACQUIRE_STATUS, display_name="acquire status")
        self._cmd_dict.add(Capability.START_AUTOSAMPLE, display_name="start autosample")
        self._cmd_dict.add(Capability.STOP_AUTOSAMPLE, display_name="stop autosample")
        self._cmd_dict.add(Capability.START_DIRECT, display_name="start direct access")
        self._cmd_dict.add(Capability.STOP_DIRECT, display_name="stop direct access")

    def _build_driver_dict(self):
        """
        Populate the driver dictionary with options
        """

        log.debug('herb: ' + 'SamiProtocol._build_driver_dict')

        self._driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

    ########################################################################
    # Command handlers.
    ########################################################################

    def _build_simple_command(self, cmd):
        """
        Build handler for basic SAMI commands.
        @param cmd the simple SAMI command to format.
        @retval The command to be sent to the device.
        """

        log.debug('herb: ' + 'SamiProtocol._build_simple_command')

        return cmd + NEWLINE

    def _build_sample_sami(self):

        log.debug('herb: ' + 'SamiProtocol._build_sample_sami')

        pass

    def _build_escape_boot(self):

        log.debug('herb: ' + 'SamiProtocol._build_escape_boot')

        pass

    ########################################################################
    # Response handlers.
    ########################################################################
    def _parse_response_get_status(self, response, prompt):
        log.debug('herb: ' + 'SamiProtocol._parse_response_get_status: response = ' + repr(response))
        return response

## TODO: Should be overridden in sub classes maybe?
    def _parse_response_get_config(self, response, prompt):
        log.debug('herb: ' + 'SamiProtocol._parse_response_get_config')
        return response

    def _parse_response_set_config(self, response, prompt):
## TODO: Should return a 4 character checksum?
        log.debug('herb: ' + 'SamiProtocol._parse_response_set_config')
        pass

    def _parse_response_erase_all(self, response, prompt):
## TODO: Should return a value, 4 characters?
        log.debug('herb: ' + 'SamiProtocol._parse_response_erase_all')
        pass

## TODO: Should be overridden in sub classes maybe?
    def _parse_response_blank_sample_sami(self, response, prompt):
        log.debug('herb: ' + 'SamiProtocol._parse_response_sample_sami')
        pass

    def _parse_response_sample_sami(self, response, prompt):
        log.debug('herb: ' + 'SamiProtocol._parse_response_sample_sami')
        pass

    ########################################################################
    # Private helpers.
    ########################################################################
    def _wakeup(self, timeout, delay=1):

        # Send newline to wake up instrument.
        log.debug('herb: ' + 'SamiProtocol._wakeup: Send newline to wake up')
        self._do_cmd_direct(NEWLINE)

##    @staticmethod
##    def _discover():
    def _discover(self):
        """
        Discover current state; can be UNKNOWN, COMMAND or DISCOVER
        @retval (next_state, result)
        """

        log.debug('herb: ' + 'SamiProtocol._discover')

        # Exit states can be either COMMAND, DISCOVER or back to UNKNOWN.
        next_state = None
        next_agent_state = None

        log.debug("_discover")

        # Set response timeout to 10 seconds. Should be immediate if
        # communications are enabled and the instrument is not sampling.
        # Otherwise, sampling can take up to ~3 minutes to complete. Partial
        # strings are output during that time period.

        # Make sure automatic-status updates are off. This will stop the
        # broadcast of information while we are trying to get data.
        log.debug('herb: ' + 'SamiProtocol._discover: STOP_STATUS_PERIODIC')
        self._do_cmd_no_resp(SamiInstrumentCommand.STOP_STATUS)

## TODO: Is this delay needed?  Instrument doesn't seem to like 2 commands sent quickly in secession.
        time.sleep(1)

        log.debug('herb: ' + 'SamiProtocol._discover: GET_STATUS')

## TODO: Catch and handle timeout exception, will need to retry since instrument is not always fully awake

        # Acquire the current instrument status
        status = self._do_cmd_resp(SamiInstrumentCommand.GET_STATUS, timeout=10, response_regex=REGULAR_STATUS_REGEX_MATCHER)
        log.debug('herb: ' + 'SamiProtocol._discover: status = ' + status)

        time.sleep(1)

        #Erase memory before setting configuration
        ## TODO: Should handle response, not a direct command
        self._do_cmd_direct(SamiInstrumentCommand.ERASE_ALL + NEWLINE)

        time.sleep(1)

## TODO: Execute send configuration string sequence.  Note periodic status must be stopped upon configuration.
        configuration_string = self._build_configuration_string_specific()

        # Send the configuration string
        self._do_cmd_resp(SamiInstrumentCommand.SET_CONFIG, timeout=10, response_regex=NEW_LINE_REGEX_MATCHER)
        # Important: Need to do right after to prevent bricking
        self._do_cmd_direct(configuration_string + CONFIG_TERMINATOR + NEWLINE)

## TODO: Make sure auto status is stopped again

        time.sleep(1)

        log.debug('herb: ' + 'SamiProtocol._discover: STOP_STATUS_PERIODIC again')
        self._do_cmd_no_resp(SamiInstrumentCommand.STOP_STATUS)

## TODO: Get configuration and verify it's set correctly, if not an exception is raised

        time.sleep(1)

## TODO: Verify configuration is set correctly
        self._verify_configuration_string(configuration_string)

        time.sleep(1)

## TODO: Remove, just here for testing purposes.
##        self._take_blank_sample()
##        log.debug('herb: ' + 'SamiProtocol._discover: sleeping awaiting blank sample')
##        time.sleep(115)

## TODO: Move this code somewhere else, perhaps make this an exception catchall?
        if status is None:
            # No response received in the timeout period, or response that does
            # not match the status string format is received. In either case,
            # we assume the unit is sampling and transition to a new state,
            # WAITING, to confirm or deny.

            log.debug('herb: ' + 'SamiProtocol._discover: Status is none')

            next_state = ProtocolState.WAITING
            next_agent_state = ResourceAgentState.BUSY
        else:
            # Unit is powered on and ready to accept commands, etc.

            log.debug('herb: ' + 'SamiProtocol._discover: Move to command state')

            next_state = ProtocolState.COMMAND
##            next_agent_state = ResourceAgentState.IDLE
            next_agent_state = ResourceAgentState.COMMAND

        log.debug("_discover. result start: %s" % next_state)
        return (next_state, next_agent_state)

    @staticmethod
    def _int_to_hexstring(val, slen):
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

        log.debug('herb: ' + 'SamiProtocol._int_to_hexstring')

        if not isinstance(val, int):
            raise InstrumentParameterException('Value %s is not an integer.' % str(val))
        elif not isinstance(slen, int):
            raise InstrumentParameterException('Value %s is not an integer.' % str(slen))
        else:
            hexstr = format(val, 'X')
            return hexstr.zfill(slen)

    def _current_sami_time(self):
        """
        Create a GMT timestamp in seconds using January 1, 1904 as the Epoch
        @retval an integer value representing the number of seconds since
            January 1, 1904.
        """

        log.debug('herb: ' + 'SamiProtocol._current_sami_time')

        gmt_time_tuple = time.gmtime()
        gmt_seconds_since_epoch = time.mktime(gmt_time_tuple)
        sami_seconds_since_epoch = gmt_seconds_since_epoch + SAMI_TO_UNIX

        return sami_seconds_since_epoch

    def _current_sami_time_hex_str(self):
        """
        Get current GMT time since SAMI epoch, January 1, 1904
        @retval an 8 character hex string representing the GMT number of seconds
        since January 1, 1904.
        """
        log.debug('herb: ' + 'SamiProtocol._current_sami_time_hex_str')

        sami_seconds_since_epoch = self._current_sami_time()
        sami_seconds_hex_string = format(int(sami_seconds_since_epoch), 'X')
        sami_seconds_hex_string = sami_seconds_hex_string.zfill(8)

        return sami_seconds_hex_string

    def _get_config_value_str(self, param):
        value = self._param_dict.get_config_value(param)
        log.debug('herb: ' + 'SamiProtocol._get_config_value_str(): ' + param + ' = ' + str(value))
        value_str = self._param_dict.format(param, value)
        log.debug('herb: ' + 'SamiProtocol._get_config_value_str(): ' + param + ' = ' + value_str)

        return value_str

    @staticmethod
    def _add_config_str_padding(configuration_string):

        config_string_length_no_padding = len(configuration_string)
        log.debug('herb: ' + 'Protocol._add_config_str_padding(): config_string_length_no_padding = ' + str(config_string_length_no_padding))

        zero_padding_length = CONFIG_WITH_0_PADDING - config_string_length_no_padding
        zero_padding = '0' * zero_padding_length
        configuration_string += zero_padding
        config_string_length_0_padding = len(configuration_string)
        log.debug('herb: ' + 'Protocol._add_config_str_padding(): config_string_length_0_padding = ' + str(config_string_length_0_padding))

        f_padding_length = CONFIG_WITH_0_AND_F_PADDING - config_string_length_0_padding
        f_padding = 'F' * f_padding_length
        configuration_string += f_padding
        config_string_length_0_and_f_padding = len(configuration_string)
        log.debug('herb: ' + 'Protocol._add_config_str_padding(): config_string_length_0_and_f_padding = ' + str(config_string_length_0_and_f_padding))

        return configuration_string

# TODO: During refactoring build configuration string as a list and join for efficiency
    def _build_configuration_string_base(self, parameter_list):

        configuration_string = ''

        # LAUNCH_TIME always set to current GMT sami time
        sami_time_hex_str = self._current_sami_time_hex_str()
        log.debug('herb: ' + 'Protocol._build_configuration_string_base(): LAUNCH TIME = ' + sami_time_hex_str)
        configuration_string += sami_time_hex_str

        for param in parameter_list:
            config_value_hex_str = self._get_config_value_str(param)
            configuration_string += config_value_hex_str

        config_string_length_no_padding = len(configuration_string)
        log.debug('herb: ' + 'Protocol._build_configuration_string_base(): config_string_length_no_padding = ' + str(config_string_length_no_padding))

        configuration_string = SamiProtocol._add_config_str_padding(configuration_string)

        return configuration_string

    def _build_configuration_string_specific(self):
        """
        Overridden by device specific subclasses.
        """

        raise NotImplementedException()

    # def _verify_configuration_string_specific(self, configuration_string):
    #     """
    #     Overridden by device specific subclasses.
    #     """
    #
    #    raise NotImplementedException()
    #
    #     pass

    def _get_configuration_string_regex(self):
        """
        Overridden by device specific subclasses.
        """

        raise NotImplementedException()

        pass

    def _get_blank_sample_timeout(self):
        """
        Overridden by device specific subclasses.
        """

        raise NotImplementedException()

        pass

    def _get_sample_timeout(self):
        """
        Overridden by device specific subclasses.
        """

        raise NotImplementedException()

        pass

    def _verify_configuration_string(self, configuration_string):

        log.debug('herb: ' + 'Protocol._verify_configuration_string()')

        configuration_string_regex = self._get_configuration_string_regex()

        instrument_configuration_string = self._do_cmd_resp(SamiInstrumentCommand.GET_CONFIG, timeout=10, response_regex=configuration_string_regex)

        if configuration_string == instrument_configuration_string.strip(NEWLINE):
            log.debug('herb: ' + 'Protocol._verify_configuration_string(): CONFIGURATION STRING IS VALID')
        else:
            ## TODO: Throw an exception
            log.error('herb: ' + 'Protocol._verify_configuration_string(): CONFIGURATION STRING IS INVALID')
            raise InstrumentProtocolException("Invalid Configuration String")
        pass

## TODO: Execute asynchronous commands to get samples.
    def _take_sample(self):
        ## An exception is raised if timeout is hit.
        ## Should return immediately
        log.debug('herb: ' + 'Protocol._take_sample()')
        return self._do_cmd_resp(SamiInstrumentCommand.ACQUIRE_SAMPLE_SAMI, timeout = 10, response_regex=BLANK_SAMPLE_RETURN_REGEX_MATCHER)

    def _take_blank_sample(self):

        ## An exception is raised if timeout is hit.
        ## Should return immediately
        log.debug('herb: ' + 'Protocol._take_blank_sample()')
        return self._do_cmd_resp(SamiInstrumentCommand.ACQUIRE_BLANK_SAMPLE_SAMI, timeout = 10, response_regex=BLANK_SAMPLE_RETURN_REGEX_MATCHER)

## TODO: Use in test app to test first
    @staticmethod
    def calc_crc(s, num_points):
        """
        Compute a checksum for a Sami data record or control record string.

        The '*' (character 1) and unique identifying byte (byte 1,
        characters 2 & 3) at the beginning should be excluded from the
        checksum calculation as well as the checksum value itself (last
        byte, last 2 characters). It should include the record length
        (byte 2, characters 4 & 5).

        Note that this method does NOT calculate the checksum on the
        configuration string that is returned during instrument
        configuration.

        @author Chris Center
        @param s: string for check-sum analysis.
        @param num_points: number of bytes (each byte is 2-chars).
        """

        log.debug('herb: ' + 'SamiProtocol.calc_crc')

        cs = 0
        k = 0
        for i in range(num_points):
            value = int(s[k:k+2], 16)  # 2-chars per data point
            cs = cs + value
            k = k + 2
        cs = cs & 0xFF
        return(cs)