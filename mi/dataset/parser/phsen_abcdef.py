#!/usr/bin/env python

"""
@package mi.dataset.parser.phsen_abcdef
@file marine-integrations/mi/dataset/parser/phsen_abcdef.py
@author Joseph Padula
@brief Parser for the phsen_abcdef recovered dataset driver
Release notes:

initial release
"""

__author__ = 'Joe Padula'
__license__ = 'Apache 2.0'

import copy
import re
import time
from functools import partial
from dateutil import parser

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue
from mi.core.exceptions import SampleException, DatasetParserException, UnexpectedDataException
from mi.dataset.dataset_parser import BufferLoadingParser
from mi.core.instrument.chunker import StringChunker

# ASCII File with records separated by carriage return, newline, or carriage return - line feed
NEW_LINE = r'[\n\r]+'

RECORD_REGEX = r'.*'
RECORD_REGEX += NEW_LINE

RECORD_MATCHER = re.compile(RECORD_REGEX)

START_OF_DATA_REGEX = r'^:Data'
START_OF_DATA_MATCHER = re.compile(START_OF_DATA_REGEX)

# This is an example of the input string for a PH record
#   10 -> Type is pH
#   3456975600 -> Time = 2013-07-18 7:00:00
#   2276 -> Starting Thermistor
#
#   Reference Light measurements
#   2955 2002 2436 2495
#   2962 1998 2440 2492
#   2960 2001 2440 2494
#   2964 2002 2444 2496

#   Light measurements
#   2962 2004 2438 2496
#   2960 2002 2437 2494
#   ...
#   2962 1585 2439 2171
#   0 -> Not Used
#   2857 -> Battery
#   2297 -> End Thermistor
#

PH_REGEX = r'(10)'          # record type
PH_REGEX += r'\t(\d+)'      # time
PH_REGEX += r'\t(\d+)'      # starting thermistor
PH_REGEX += r'\t(\d+\t){16}'  # reference light measurements
PH_REGEX += r'(\d+\t){92}'  # light measurements
PH_REGEX += r'\d+'          # unused
PH_REGEX += r'\t(\d+)'      # battery status
PH_REGEX += r'\t(\d+)'      # end thermistor
PH_REGEX += '\t*'
PH_REGEX += NEW_LINE

PH_MATCHER = re.compile(PH_REGEX)

CONTROL_REGEX = r'(\d{3})\t'
CONTROL_REGEX += r'\d+\t'
CONTROL_REGEX += r'\d+\t'
CONTROL_REGEX += r'\d+\t'
CONTROL_REGEX += r'\d+\t'
CONTROL_REGEX += r'\d+'
CONTROL_MATCHER = re.compile(CONTROL_REGEX)

PH_REFERENCE_MEASUREMENTS = 16
PH_LIGHT_MEASUREMENTS = 92

# Control type consists of Info (128 - 191) and Error (192 - 255). Some of these are excluded
# as they are a different length and are in BATTERY_CONTROL_TYPE and DATA_CONTROL_TYPE
CONTROL_TYPE = [128, 129, 131, 133, 134, 135, 190, 194, 195, 196, 197, 198, 254]
# Control msg with battery voltage field
BATTERY_CONTROL_TYPE = [192, 193]
# Control msg that may have a test data field
DATA_CONTROL_TYPE = [191, 255]

# Control msg with battery field
BATTERY_CONTROL_MSG_NUM_FIELDS = 7
# Note: control msg with test data field will have 7 fields, otherwise 6
DATA_CONTROL_MSG_NUM_FIELDS = 7
# Number of fields in the other control messages (not including battery or data type)
CONTROL_MSG_NUM_FIELDS = 6

TIMESTAMP_FIELD = 1


def time_to_unix_time(sec_since_1904):
    """
    Convert between seconds since 1904 into unix time (epoch time)
    @param sec_since_1904 ascii string of seconds since Jan 1 1904
    @retval sec_since_1970 epoch time
    """
    local_dt_1904 = parser.parse("1904-01-01T00:00:00.00Z")
    elapse_1904 = float(local_dt_1904.strftime("%s.%f"))
    sec_since_1970 = sec_since_1904 + elapse_1904 - time.timezone
    return sec_since_1970


class StateKey(BaseEnum):
    POSITION = 'position'  # hold the current file position
    START_OF_DATA = 'start_of_data'


class DataParticleType(BaseEnum):
    INSTRUMENT = 'phsen_abcdef_instrument'
    METADATA = 'phsen_abcdef_metadata'


class PhsenRecoveredDataParticleKey(BaseEnum):
    RECORD_TYPE = 'record_type'
    RECORD_TIME = 'record_time'
    VOLTAGE_BATTERY = 'voltage_battery'


class PhsenRecoveredInstrumentDataParticleKey(PhsenRecoveredDataParticleKey):
    THERMISTOR_START = 'thermistor_start'
    REFERENCE_LIGHT_MEASUREMENTS = 'reference_light_measurements'
    LIGHT_MEASUREMENTS = 'light_measurements'
    THERMISTOR_END = 'thermistor_end'


class PhsenRecoveredInstrumentDataParticle(DataParticle):
    """
    Class for parsing data from the phsen_abcdef ph data set
    """

    _data_particle_type = DataParticleType.INSTRUMENT

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):
        super(PhsenRecoveredInstrumentDataParticle, self).__init__(raw_data,
                                                                   port_timestamp,
                                                                   internal_timestamp,
                                                                   preferred_timestamp,
                                                                   quality_flag,
                                                                   new_sequence)

        # use the timestamp from the sio header as internal timestamp
        sec_since_1904 = int(self.raw_data[TIMESTAMP_FIELD])
        unix_time = time_to_unix_time(sec_since_1904)
        self.set_internal_timestamp(unix_time=unix_time)

    def _build_parsed_values(self):
        """
        Take a record in the ph data format and turn it into
        a particle with the instrument tag.
        @throws SampleException If there is a problem with sample creation
        """
        field = 0
        record_type = self.raw_data[field]

        field += 1
        record_time = self.raw_data[field]

        field += 1
        starting_thermistor = self.raw_data[field]

        # Create array for reference and light measurements.
        # noinspection PyUnusedLocal
        reference_measurements = [0 for x in range(PH_REFERENCE_MEASUREMENTS)]
        for record_set in range(0, PH_REFERENCE_MEASUREMENTS):

            field += 1
            # We cast to int here as _encode_value does not cast elements in the list
            reference_measurements[record_set] = int(self.raw_data[field], 10)

        # noinspection PyUnusedLocal
        light_measurements = [0 for x in range(PH_LIGHT_MEASUREMENTS)]
        for record_set in range(0, PH_LIGHT_MEASUREMENTS):

            field += 1
            # We cast to int here as _encode_value does not cast elements in the list
            light_measurements[record_set] = int(self.raw_data[field], 10)

        # Skip unused
        field += 2

        battery_voltage = self.raw_data[field]

        field += 1
        end_thermistor = self.raw_data[field]

        result = [self._encode_value(PhsenRecoveredDataParticleKey.RECORD_TYPE, record_type, int),
                  self._encode_value(PhsenRecoveredDataParticleKey.RECORD_TIME, record_time, int),
                  self._encode_value(PhsenRecoveredInstrumentDataParticleKey.THERMISTOR_START, starting_thermistor,
                                     int),
                  self._encode_value(PhsenRecoveredInstrumentDataParticleKey.REFERENCE_LIGHT_MEASUREMENTS,
                                     reference_measurements, list),
                  self._encode_value(PhsenRecoveredInstrumentDataParticleKey.LIGHT_MEASUREMENTS, light_measurements,
                                     list),
                  self._encode_value(PhsenRecoveredDataParticleKey.VOLTAGE_BATTERY, battery_voltage, int),
                  self._encode_value(PhsenRecoveredInstrumentDataParticleKey.THERMISTOR_END, end_thermistor, int)]
        return result


class PhsenRecoveredMetadataDataParticleKey(PhsenRecoveredDataParticleKey):
    CLOCK_ACTIVE = 'clock_active'
    RECORDING_ACTIVE = 'recording_active'
    RECORD_END_TIME = 'record_end_on_time'
    RECORD_MEMORY_FULL = 'record_memory_full'
    RECORD_END_ON_ERROR = 'record_end_on_error'
    DATA_DOWNLOAD_OK = 'data_download_ok'
    FLASH_MEMORY_OPEN = 'flash_memory_open'
    BATTERY_LOW_PRESENT = 'battery_low_prestart'
    BATTERY_LOW_MEASUREMENT = 'battery_low_measurement'
    BATTERY_LOW_BLANK = 'battery_low_blank'
    BATTERY_LOW_EXTERNAL = 'battery_low_external'
    EXTERNAL_DEVICE1_FAULT = 'external_device1_fault'
    EXTERNAL_DEVICE2_FAULT = 'external_device2_fault'
    EXTERNAL_DEVICE3_FAULT = 'external_device3_fault'
    FLASH_ERASED = 'flash_erased'
    POWER_ON_INVALID = 'power_on_invalid'
    NUM_DATA_RECORDS = 'num_data_records'
    NUM_ERROR_RECORDS = 'num_error_records'
    NUM_BYTES_STORED = 'num_bytes_stored'


class PhsenRecoveredMetadataDataParticle(DataParticle):
    """
    Class for parsing data from the phsen_abcdef control data set
    """

    _data_particle_type = DataParticleType.METADATA

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):
        super(PhsenRecoveredMetadataDataParticle, self).__init__(raw_data,
                                                                 port_timestamp,
                                                                 internal_timestamp,
                                                                 preferred_timestamp,
                                                                 quality_flag,
                                                                 new_sequence)

        # use the timestamp from the sio header as internal timestamp
        sec_since_1904 = int(self.raw_data[TIMESTAMP_FIELD])
        unix_time = time_to_unix_time(sec_since_1904)
        self.set_internal_timestamp(unix_time=unix_time)

    def _build_parsed_values(self):
        """
        Take a record in the control data format and turn it into
        a particle with the metadata tag.
        @throws SampleException If there is a problem with sample creation
        """

        field = 0
        record_type = self.raw_data[field]

        field += 1
        record_time = self.raw_data[field]

        field += 1
        # the flags are individual bits and must be encoded outside of the _encode_value function.
        flags = int(self.raw_data[field], 10)

        field += 1
        num_data_records = self.raw_data[field]

        field += 1
        num_error_records = self.raw_data[field]

        field += 1
        num_bytes_stored = self.raw_data[field]

        result = [self._encode_value(PhsenRecoveredDataParticleKey.RECORD_TYPE, record_type, int),
                  self._encode_value(PhsenRecoveredDataParticleKey.RECORD_TIME, record_time, int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.CLOCK_ACTIVE, flags & 0x1, int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.RECORDING_ACTIVE, (flags >> 1) & 0x1, int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.RECORD_END_TIME, (flags >> 2) & 0x1, int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.RECORD_MEMORY_FULL, (flags >> 3) & 0x1, int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.RECORD_END_ON_ERROR, (flags >> 4) & 0x1,
                                     int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.DATA_DOWNLOAD_OK, (flags >> 5) & 0x1, int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.FLASH_MEMORY_OPEN, (flags >> 6) & 0x1, int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.BATTERY_LOW_PRESENT, (flags >> 7) & 0x1,
                                     int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.BATTERY_LOW_MEASUREMENT, (flags >> 8) & 0x1,
                                     int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.BATTERY_LOW_BLANK, (flags >> 9) & 0x1, int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.BATTERY_LOW_EXTERNAL, (flags >> 10) & 0x1,
                                     int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.EXTERNAL_DEVICE1_FAULT, (flags >> 11) & 0x1,
                                     int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.EXTERNAL_DEVICE2_FAULT, (flags >> 12) & 0x1,
                                     int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.EXTERNAL_DEVICE3_FAULT, (flags >> 13) & 0x1,
                                     int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.FLASH_ERASED, (flags >> 14) & 0x1, int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.POWER_ON_INVALID, (flags >> 15) & 0x1, int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.NUM_DATA_RECORDS, num_data_records, int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.NUM_ERROR_RECORDS, num_error_records, int),
                  self._encode_value(PhsenRecoveredMetadataDataParticleKey.NUM_BYTES_STORED, num_bytes_stored, int)]

        record_type = int(record_type)
        if record_type in BATTERY_CONTROL_TYPE:
            field += 1
            battery_voltage = self.raw_data[field]
            temp_result = self._encode_value(PhsenRecoveredDataParticleKey.VOLTAGE_BATTERY, battery_voltage, int)
            result.append(temp_result)
        else:
            # This will handle anything after NUM_ERROR_RECORDS, including data in type 191 and 255.
            result.append({DataParticleKey.VALUE_ID: PhsenRecoveredDataParticleKey.VOLTAGE_BATTERY,
                           DataParticleKey.VALUE: None})
        return result


class PhsenRecoveredParser(BufferLoadingParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):

        # noinspection PyArgumentList,PyArgumentList,PyArgumentList,PyArgumentList,PyArgumentList
        super(PhsenRecoveredParser, self).__init__(config, stream_handle, state,
                                                   partial(StringChunker.regex_sieve_function,
                                                   regex_list=[RECORD_MATCHER]),
                                                   state_callback,
                                                   publish_callback,
                                                   exception_callback,
                                                   *args,
                                                   **kwargs)

        self._read_state = {StateKey.POSITION: 0, StateKey.START_OF_DATA: False}

        if state:
            self.set_state(self._state)

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to.
        @throws DatasetParserException if there is a bad state structure
        """
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not ((StateKey.POSITION in state_obj)):
            raise DatasetParserException("Missing state key %s" % StateKey.POSITION)
        if not ((StateKey.START_OF_DATA in state_obj)):
            raise DatasetParserException("Missing state key %s" % StateKey.START_OF_DATA)

        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj
        self._chunker.clean_all_chunks()

        # seek to the position
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, increment):
        """
        Increment the parser state
        @param increment The amount to increment the position by
        """
        self._read_state[StateKey.POSITION] += increment

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """
        result_particles = []
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
        self.handle_non_data(non_data, non_end, start)

        while chunk is not None:

            log.info("Chunk: ****%s****", chunk)

            self._increment_state(len(chunk))
            if not self._read_state[StateKey.START_OF_DATA]:

                log.info("In if not self._read_state[StateKey.START_OF_DATA]")

                start_of_data = START_OF_DATA_MATCHER.match(chunk)
                if start_of_data:
                    self._read_state[StateKey.START_OF_DATA] = True
            else:

                # if this chunk is a data match process it, otherwise it is a metadata record which is ignored
                ph_match = PH_MATCHER.match(chunk)
                control_match = CONTROL_MATCHER.match(chunk)

                if ph_match:
                    fields = chunk.split()

                    # particle-ize the data block received, return the record
                    sample = self._extract_sample(PhsenRecoveredInstrumentDataParticle,
                                                  None, fields, None)

                    if sample:
                        # create particle
                        result_particles.append((sample, copy.copy(self._read_state)))

                elif control_match:
                    record_type = int(control_match.group(1), 10)
                    fields = chunk.split()
                    if record_type in CONTROL_TYPE or record_type in BATTERY_CONTROL_TYPE \
                            or record_type in DATA_CONTROL_TYPE:
                        # Check the length of the battery control messages first.
                        if record_type in BATTERY_CONTROL_TYPE and len(fields) != BATTERY_CONTROL_MSG_NUM_FIELDS:
                                error_str = 'Unexpected num of fields (%d) for control record type (battery) %d'
                                log.warn(error_str, len(fields), record_type)
                                self._exception_callback(SampleException(error_str % (len(fields), record_type)))

                        # DATA_CONTROL_TYPE messages may or may not have a data field
                        elif record_type in DATA_CONTROL_TYPE and \
                                (len(fields) != DATA_CONTROL_MSG_NUM_FIELDS) and \
                                (len(fields) != DATA_CONTROL_MSG_NUM_FIELDS-1):
                                error_str = 'Unexpected num of fields (%d) for control record type (data) %d'
                                log.warn(error_str, len(fields), record_type)
                                self._exception_callback(SampleException(error_str % (len(fields), record_type)))

                        elif record_type in CONTROL_TYPE and len(fields) != CONTROL_MSG_NUM_FIELDS:
                            error_str = 'Unexpected number of fields (%d) for control record type %d'
                            log.warn(error_str, len(fields), record_type)
                            self._exception_callback(SampleException(error_str % (len(fields), record_type)))

                        else:
                            # particle-ize the data block received, return the record
                            sample = self._extract_sample(PhsenRecoveredMetadataDataParticle,
                                                          None, fields, None)

                            if sample:
                                # create particle
                                result_particles.append((sample, copy.copy(self._read_state)))
                    else:
                        # Matched by REGEX but not a supported control type
                        error_str = 'Invalid Record Type %d'
                        log.warn(error_str, record_type)
                        self._exception_callback(SampleException(error_str % record_type))
                else:
                    # Non-PH or non-Control type or REGEX not matching PH/Control record
                    error_str = 'REGEX does not match PH or Control record %s'
                    log.warn(error_str, chunk)
                    self._exception_callback(SampleException(error_str % chunk))

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            self.handle_non_data(non_data, non_end, start)

        return result_particles

    def handle_non_data(self, non_data, non_end, start):
        """
        handle data in the non_data chunker queue
        @param non_data data in the non data chunker queue
        @param non_end ending index of the non_data chunk
        @param start start index of the next data chunk
        """
        # we can get non_data after our current chunk, check that this chunk is before that chunk
        if non_data is not None and non_end <= start:
            log.error("Found %d bytes of unexpected non-data:%s", len(non_data), non_data)
            self._exception_callback(UnexpectedDataException("Found %d bytes of un-expected non-data:%s" %
                                                            (len(non_data), non_data)))
            self._increment_state(len(non_data))
