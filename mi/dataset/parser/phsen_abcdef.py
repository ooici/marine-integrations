#!/usr/bin/env python

"""
@package mi.dataset.parser.phsen_abcdef
@file marine-integrations/mi/dataset/parser/phsen_abcdef.py
@author Joseph Padula
@brief Parser for the phsen_abcdef recovered dataset driver
Release notes:

initial release
"""

__author__ = 'Joseph Padula'
__license__ = 'Apache 2.0'

import copy
import re
from functools import partial

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue
from mi.core.exceptions import SampleException, DatasetParserException, UnexpectedDataException
from mi.dataset.dataset_parser import BufferLoadingParser
from mi.core.instrument.chunker import StringChunker

# ASCII File with records separated by new line
RECORD_REGEX = r'.*[\n|\r\n]'
RECORD_MATCHER = re.compile(RECORD_REGEX)

START_OF_DATA_REGEX = r'^:Data'
START_OF_DATA_MATCHER = re.compile(START_OF_DATA_REGEX)


# This is an example of the input string
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

PH_REGEX = r'(10)'          # record type
PH_REGEX += r'\t(\d{10})'   # time
PH_REGEX += r'\t(\d+)'      # starting thermistor
PH_REGEX += r'\t(\d+\t){16}'  # reference light measurements
PH_REGEX += r'(\d+\t){92}'  # light measurements
PH_REGEX += r'\d+'          # unused
PH_REGEX += r'\t(\d+)'      # battery status
PH_REGEX += r'\t(\d+)'      # end thermistor
PH_REGEX += '\t*(\r\n?|\n)'

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

BATTERY_CONTROL_TYPE = [192, 193]
TIMESTAMP_FIELD = 1


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

    def _build_parsed_values(self):
        """
        Take a record in the ph data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        field = 0
        record_type = int(self.raw_data[field], 10)

        field += 1
        record_time = int(self.raw_data[field], 10)

        field += 1
        starting_thermistor = int(self.raw_data[field], 10)

        # Create array for reference and light measurements.
        reference_measurements = [0 for x in range (PH_REFERENCE_MEASUREMENTS)]
        for record_set in range(0, PH_REFERENCE_MEASUREMENTS):

            field += 1
            reference_measurements[record_set] = int(self.raw_data[field], 10)

        light_measurements = [0 for x in range (PH_LIGHT_MEASUREMENTS)]
        for record_set in range(0, PH_LIGHT_MEASUREMENTS):

            field += 1
            light_measurements[record_set]  = int(self.raw_data[field], 10)


        # Skip unused
        field += 2

        battery_voltage = int(self.raw_data[field], 10)

        field += 1
        end_thermistor = int(self.raw_data[field], 10)

        result = [self._encode_value(PhsenRecoveredDataParticleKey.RECORD_TYPE, record_type, int),
                  self._encode_value(PhsenRecoveredDataParticleKey.RECORD_TIME, record_time, int),
                  self._encode_value(PhsenRecoveredInstrumentDataParticleKey.THERMISTOR_START, starting_thermistor, int),
                  self._encode_value(PhsenRecoveredInstrumentDataParticleKey.REFERENCE_LIGHT_MEASUREMENTS,
                                     reference_measurements, list),
                  self._encode_value(PhsenRecoveredInstrumentDataParticleKey.LIGHT_MEASUREMENTS, light_measurements, list),
                  self._encode_value(PhsenRecoveredDataParticleKey.VOLTAGE_BATTERY, battery_voltage, int),
                  self._encode_value(PhsenRecoveredInstrumentDataParticleKey.THERMISTOR_END, end_thermistor, int)]

        log.debug('PhsenAbcdefParserDataParticle: particle %s', result)
        return result


class PhsenRecoveredMetdataDataParticleKey(PhsenRecoveredDataParticleKey):
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

    def _build_parsed_values(self):
        """
        Take a record in the control data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """

        field = 0
        record_type = int(self.raw_data[field], 10)

        field += 1
        record_time = int(self.raw_data[field], 10)

        field += 1
        flags = int(self.raw_data[field], 10)

        field += 1
        num_data_records = int(self.raw_data[field], 10)

        field += 1
        num_error_records = int(self.raw_data[field], 10)

        field += 1
        num_bytes_stored = int(self.raw_data[field], 10)

        result = [self._encode_value(PhsenRecoveredDataParticleKey.RECORD_TYPE, record_type, int),
            self._encode_value(PhsenRecoveredDataParticleKey.RECORD_TIME, record_time, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.CLOCK_ACTIVE, flags&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.RECORDING_ACTIVE, (flags>>1)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.RECORD_END_TIME, (flags>>2)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.RECORD_MEMORY_FULL, (flags>>3)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.RECORD_END_ON_ERROR, (flags>>4)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.DATA_DOWNLOAD_OK, (flags>>5)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.FLASH_MEMORY_OPEN, (flags>>6)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.BATTERY_LOW_PRESENT, (flags>>7)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.BATTERY_LOW_MEASUREMENT, (flags>>8)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.BATTERY_LOW_BLANK, (flags>>9)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.BATTERY_LOW_EXTERNAL, (flags>>10)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.EXTERNAL_DEVICE1_FAULT, (flags>>11)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.EXTERNAL_DEVICE2_FAULT, (flags>>12)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.EXTERNAL_DEVICE3_FAULT,(flags>>13)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.FLASH_ERASED, (flags>>14)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.POWER_ON_INVALID, (flags>>15)&0x1, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.NUM_DATA_RECORDS, num_data_records, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.NUM_ERROR_RECORDS, num_error_records, int),
            self._encode_value(PhsenRecoveredMetdataDataParticleKey.NUM_BYTES_STORED, num_bytes_stored, int)]

        if record_type in BATTERY_CONTROL_TYPE:

            field += 1
            battery_voltage = int(self.raw_data[field], 10)
            temp_result = self._encode_value(PhsenRecoveredDataParticleKey, battery_voltage, int)
            result.extend(temp_result)
        else:
            # This will handle anything after NUM_ERROR_RECORDS, including data in type 191 and 255.
            result.extend({DataParticleKey.VALUE_ID: PhsenRecoveredDataParticleKey.VOLTAGE_BATTERY,
                           DataParticleKey.VALUE: None})

        log.debug('PhsenRecoveredMetadataDataParticle: particle %s', result)
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

        if state is None:
            state = {}
        if not ((StateKey.POSITION in state)):
            state[StateKey.POSITION] = 0
        if not ((StateKey.START_OF_DATA in state)):

            state[StateKey.START_OF_DATA] = False


        super(PhsenRecoveredParser, self).__init__(config,
                                            stream_handle,
                                            state,
                                           # self.sieve_function,
                                           partial(StringChunker.regex_sieve_function,
                                                    regex_list=[RECORD_MATCHER]),
                                            state_callback,
                                            publish_callback,
                                            exception_callback,
                                            *args,
                                            **kwargs)


        self._read_state = {StateKey.POSITION: 0}

        log.debug("state is %s", state)
        if state:
            self.set_state(self._state)
        log.debug("self.state is %s", self._state)
    def sieve_function(self, input_buffer):

        indices_list = []    # initialize the return list to empty

        return indices_list


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
            #log.debug('PARSER <%s>', chunk)
            self._increment_state(len(chunk))
            if not self._state[StateKey.START_OF_DATA]:

                start_of_data = START_OF_DATA_MATCHER.match(chunk)
                if start_of_data:
                    self._state[StateKey.START_OF_DATA] = True
            else:

                # if this chunk is a data match process it, otherwise it is a metadata record which is ignored
                ph_match = PH_MATCHER.match(chunk)
                control_match = CONTROL_MATCHER.match(chunk)

                if ph_match:
                    # log.debug("found a ph record %s ", ph_match.group(0))
                    fields = chunk.split()
                    log.debug("len %d fields %s", len(fields), fields)

                    # particle-ize the data block received, return the record
                    sample = self._extract_sample(PhsenRecoveredInstrumentDataParticle,
                                                  None, fields, int(fields[TIMESTAMP_FIELD], 10))

                    if sample:
                        # create particle
                        result_particles.append((sample, copy.copy(self._read_state)))
                        # log.debug("Extracting sample chunk %s with read_state: %s", chunk, self._read_state)

                elif control_match:
                    record_type = int(control_match.group(1), 10)
                    fields = chunk.split()
                    if record_type in [128, 129, 131, 133, 191, 192, 193, 255]:
                        # particle-ize the data block received, return the record
                        sample = self._extract_sample(PhsenRecoveredMetadataDataParticle,
                                                      None, fields, int(fields[TIMESTAMP_FIELD], 10))

                        if sample:
                            # create particle
                            result_particles.append((sample, copy.copy(self._read_state)))
                            # log.debug("Extracting sample chunk %s with read_state: %s", chunk, self._read_state)

                    else:
                        log.warn("Invalid Record Type %d", record_type)
                        self._exception_callback(SampleException("Invalid Record Type %d" % record_type))



            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            self.handle_non_data(non_data, non_end, start)

        log.debug('num particals %d', len(result_particles))
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

