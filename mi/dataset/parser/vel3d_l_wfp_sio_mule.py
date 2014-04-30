#!/usr/bin/env python

"""
@package mi.dataset.parser.vel3d_l_wfp_sio_mule
@file marine-integrations/mi/dataset/parser/vel3d_l_wfp_sio_mule.py
@author Steve Myerson (Raytheon)
@brief Parser for the vel3d_l_wfp dataset driver
Release notes:

Initial Release
"""

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

#import copy
import ntplib
#import re
import struct
import time

from mi.core.log import get_logger; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import \
    DatasetParserException, \
    RecoverableSampleException, \
    SampleException, \
    UnexpectedDataException

from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER

ID_VEL3D_L_WFP_SIO_MULE = 'WA'  # The type of instrument for this parser

SIO_HEADER_GROUP_ID = 1           # Header group number for instrument ID
SIO_HEADER_GROUP_DATA_LENGTH = 2  # Header group number for data length
SIO_HEADER_GROUP_TIMESTAMP = 3    # Header group number for timestamp

#
# VEL3D_L_WFP_SIO_MULE File format (this does not include the SIO header)
# Data bytes (4 bytes)
# FSI Header (279 bytes)
# FSI Record (47 bytes * N instances)
# Sensor start time (4 bytes)
# Sensor stop time (4 bytes)
# Decimation (2 bytes, optional)
#
DATA_BYTES_SIZE = 4            # byte in the Data bytes field
FSI_HEADER_SIZE = 279          # bytes in the FSI header
FSI_RECORD_SIZE = 47           # bytes in each FSI record

FSI_HEADER_SERIAL_NUMBER_OFFSET = 3    # byte offset into FSI Header
FSI_HEADER_SERIAL_NUMBER_SIZE = 4      # bytes in the serial number field

#
# FSI Record Format
# Offset  Bytes  Format   Field
#  0      1      uint8    hour
#  1      1      uint8    minute
#  2      1      uint8    second
#  3      1      uint8    month
#  4      1      uint8    day
#  5      2      uint16   year
#  7      4      float32  heading
# 11      4      float32  tx
# 15      4      float32  ty
# 19      4      float32  hx
# 23      4      float32  hy
# 27      4      float32  hz
# 31      4      float32  vp1
# 35      4      float32  vp2
# 39      4      float32  vp3
# 43      4      float32  vp4
#
FSI_RECORD_FORMAT = '<5BH10f'  # format for unpacking data from FSI records

#
# Keys to be used when generating particles.
# Instrument values are extracted from the FSI Record.
# Metadata values are extracted from the Time Record and the FSI Header.
# They are listed in order corresponding to the data record payload.
#
INDEX_PARTICLE_KEY = 0
INDEX_VALUE_TYPE = 1

INSTRUMENT_PARTICLE_KEYS = \
[
    ['vel3d_l_date_time_array', list],
    ['vel3d_l_heading',         float],
    ['vel3d_l_tx',              float],
    ['vel3d_l_ty',              float],
    ['vel3d_l_hx',              float],
    ['vel3d_l_hy',              float],
    ['vel3d_l_hz',              float],
    ['vel3d_l_vp1',             float],
    ['vel3d_l_vp2',             float],
    ['vel3d_l_vp3',             float],
    ['vel3d_l_vp4',             float]
]

METADATA_PARTICLE_KEYS = \
[
    ['vel3d_l_time_on',           int],
    ['vel3d_l_time_off',          int],
    ['vel3d_l_decimation_factor', int],
    ['vel3d_l_serial_number',     int],
    ['vel3d_l_number_of_records', int]
]
DATE_TIME_ARRAY = 'vel3d_l_date_time_array'  # This one needs to be special-cased
DATE_TIME_SIZE = 6                     # 6 bytes for the output date time field

DECIMATION_RECORD_SIZE = 10  # bytes in time fields plus decimation field
DECIMATION_FORMAT = '>2IH'   # 2 uint32, 1 uint16
TIME_RECORD_SIZE = 8         # bytes in time fields
TIME_FORMAT = '>2I'          # 2 uint32
FIELD_TIME_ON = 0
FIELD_TIME_OFF = 1
FIELD_DECIMATION = 2
FIELD_SERIAL_NUMBER = 3
FIELD_NUMBER_OF_RECORDS = 4
FIELD_METADATA_TIMESTAMP = 5

PARTICLE_TYPE_INSTRUMENT = 1
PARTICLE_TYPE_METADATA = 2


class Vel3dLWfpSioMuleStateKey(BaseEnum):
    POSITION = 'position'  # holds the file position


class Vel3dLWfpSioMuleDataParticleType(BaseEnum):
    INSTRUMENT_PARTICLE = 'vel3d_l_wfp_instrument'
    METADATA_PARTICLE = 'vel3d_l_wfp_metadata'


class Vel3dLWfpSioMuleInstrumentParticle(DataParticle):
    """
    Class for generating vel3d_l_wfp instrument particles.
    """

    _data_particle_type = Vel3dLWfpSioMuleDataParticleType.INSTRUMENT_PARTICLE
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        #
        # Generate an Instrument data particle.
        # Note that raw_data already contains the individual fields
        # extracted and unpacked from the data record.
        #
        particle = []
        field_index = 0
        fields = self.raw_data

        for x in range(0, len(INSTRUMENT_PARTICLE_KEYS)):
            key = INSTRUMENT_PARTICLE_KEYS[x][INDEX_PARTICLE_KEY]
            data_type = INSTRUMENT_PARTICLE_KEYS[x][INDEX_VALUE_TYPE]

            #
            # The date time array data must be special-cased since multiple
            # values from the parsed values are used for a single particle value.
            #
            if key == DATE_TIME_ARRAY:

                #
                # When generating the date time array field,
                # use these values to generate a timestamp for this particle.
                #
                hour = fields[field_index]
                minute = fields[field_index + 1]
                second = fields[field_index + 2]
                month = fields[field_index + 3]
                day = fields[field_index + 4]
                year = fields[field_index + 5]

                timestamp = (year, month, day, hour, minute, second, 0, 0, 0)
                elapsed_seconds = time.mktime(timestamp)
                ntp_time = ntplib.system_to_ntp_time(elapsed_seconds)
                self.set_internal_timestamp(timestamp=ntp_time)
                log.info("INST ntp_time %f", ntp_time)

                #
                # Generate the date time array to be stored in the particle.
                #
                date_time_array = [year, month, day, hour, minute, second]
                particle_value = self._encode_value(key, date_time_array, data_type)
                field_index += DATE_TIME_SIZE

            else:
                #
                # Other particle values are extracted directly from the
                # previously parsed fields.
                #
                particle_value = self._encode_value(key, fields[field_index], data_type)
                field_index += 1

            particle.append(particle_value)

        return particle


class Vel3dLWfpSioMuleMetadataParticle(DataParticle):
    """
    Class for generating vel3d_l_wfp metadata particles.
    """

    _data_particle_type = Vel3dLWfpSioMuleDataParticleType.METADATA_PARTICLE

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        #
        # Generate a Metadata data particle.
        # Note that raw_data already contains the individual fields
        # extracted and unpacked from the metadata record.
        #
        particle = []
        field_index = 0
        fields = self.raw_data

        #
        # The timestamp from the SIO Header will be used as the timestamp
        # for the metadata stream record.
        #
        seconds = fields[FIELD_METADATA_TIMESTAMP]
        ntp_time = ntplib.system_to_ntp_time(seconds)
        self.set_internal_timestamp(timestamp=ntp_time)
        log.info("META ntp_time %f", ntp_time)

        #
        # Extract the metadata particle fields from the parsed values.
        #
        for x in range(0, len(METADATA_PARTICLE_KEYS)):
            key = METADATA_PARTICLE_KEYS[x][INDEX_PARTICLE_KEY]

            #
            # There is a bug in encode_value.
            # If the value is 'None', encode_value chokes.
            #
            if fields[field_index] is None:
                particle.append({DataParticleKey.VALUE_ID: key,
                                 DataParticleKey.VALUE: None})
            else:
                particle_value = self._encode_value(key, fields[field_index],
                    METADATA_PARTICLE_KEYS[x][INDEX_VALUE_TYPE])
                particle.append(particle_value)
            field_index += 1

        return particle


class Vel3dLWfpSioMuleParser(SioMuleParser):

    def __init__(self, config, state, stream_handle,
                 state_callback, publish_callback, exception_callback):
        """
        @param config The configuration parameters to feed into the parser
        @param state The location in the file to start parsing from.
           This reflects what has already been published.
        @param stream_handle An already open file-like file handle
        @param state_callback The callback method from the agent driver
           (ultimately the agent) to call back when a state needs to be
           updated
        @param publish_callback The callback from the agent driver (and
           ultimately from the agent) where we send our sample particle to
           be published into ION
        @param exception_callback The callback from the agent driver to
           send an exception to
        """
        super(Vel3dLWfpSioMuleParser, self).__init__(config, stream_handle, state,
            self.sieve_function, state_callback, publish_callback,
            exception_callback)

    def handle_non_data(self, non_data, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # if non-data is expected, handle it here, otherwise it is an error
        if non_data is not None and non_end <= start:
            # if this non-data is an error, send an UnexpectedDataException and increment the state
            self._increment_state(len(non_data))
            # if non-data is a fatal error, directly call the exception, if it is not use the _exception_callback
            self._exception_callback(UnexpectedDataException(
                "Found %d bytes of un-expected non-data %s" % (len(non_data), non_data)))

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
            sample_count = 0
            fields = self.process_chunk(chunk)
            if len(fields) > 0:
                for x in range(0, len(fields)):
                    particle_type = fields[x][0]
                    #log.info("XXX Particle %d", particle_type)
                    #log.info("%s", str(fields[x][1]))

                    if particle_type == PARTICLE_TYPE_INSTRUMENT:
                        particle_class = Vel3dLWfpSioMuleInstrumentParticle
                    else:
                        particle_class = Vel3dLWfpSioMuleMetadataParticle

                    # particle-ize the data block received, return the record
                    sample = self._extract_sample(particle_class, None,
                        fields[x][1], 0)
                    if sample:
                        # create particle
                        result_particles.append(sample)
                        sample_count += 1

            # keep track of how many samples were found in this chunk
            self._chunk_sample_count.append(sample_count)

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            self.handle_non_data(non_data, non_end, start)

        return result_particles

    def process_chunk(self, chunk):
        """
        This function processes a chunk received from the chunker.
        Parameters:
          chunk - the input chunk from the chunker
        Returns:
          A list of tuples containing the parsed values from the chunk.
        """
        particle_fields = []
        header = SIO_HEADER_MATCHER.match(chunk)
        if header.group(SIO_HEADER_GROUP_ID) == ID_VEL3D_L_WFP_SIO_MULE:

            #
            # Extract the POSIX timestamp from the SIO Header.
            #
            sio_timestamp = int(header.group(SIO_HEADER_GROUP_TIMESTAMP), 16)

            #
            # Skip past the SIO Header and the Data Bytes field
            # to get to the start of the FSI Header.
            #
            start_index = header.end(0) + DATA_BYTES_SIZE

            #
            # Extract the serial number from the FSI Header.
            #
            serial_number_start = start_index + FSI_HEADER_SERIAL_NUMBER_OFFSET
            serial_number = struct.unpack('<I',
                chunk[serial_number_start :
                      serial_number_start + FSI_HEADER_SERIAL_NUMBER_SIZE])[0]

            #
            # Skip past the FSI Header to get to the first FSI data record.
            #
            start_index += FSI_HEADER_SIZE

            #
            # Calculate the number of bytes remaining to be processed.
            # The trailing 0x03 needs to be excluded.
            #
            bytes_remaining = len(chunk) - start_index - 1

            #
            # Calculate the expected number of FSI records.
            #
            expected_records = bytes_remaining / FSI_RECORD_SIZE

            #
            # As long as there is more data in the chunk.
            #
            records_processed = 0
            metadata_found = False
            while bytes_remaining > 0:

                #
                # If there are enough bytes to comprise an FSI record,
                # extract the fields from the FSI record.
                #
                if bytes_remaining >= FSI_RECORD_SIZE:
                    fields = []
                    particle_type = PARTICLE_TYPE_INSTRUMENT
                    fields.append(particle_type)

                    fields.append(struct.unpack(FSI_RECORD_FORMAT,
                        chunk[start_index : start_index + FSI_RECORD_SIZE]))
                    bytes_remaining -= FSI_RECORD_SIZE
                    start_index += FSI_RECORD_SIZE
                    records_processed += 1

                #
                # Once all the FSI records have been processed,
                # check for a decimation or time record.
                # If there are enough bytes to comprise a decimation record
                # or a time record, extract the fields from the record.
                #
                elif records_processed == expected_records and \
                    not metadata_found and \
                    (bytes_remaining == DECIMATION_RECORD_SIZE or
                    bytes_remaining == TIME_RECORD_SIZE):

                    #
                    # If it's a decimation record, extract time on, time off
                    # and the decimation factor.
                    #
                    fields = []
                    particle_type = PARTICLE_TYPE_METADATA
                    fields.append(particle_type)

                    if bytes_remaining == DECIMATION_RECORD_SIZE:
                        metadata = struct.unpack(DECIMATION_FORMAT,
                            chunk[start_index : start_index + bytes_remaining])
                        metadata_list = list(metadata)
                        bytes_remaining -= DECIMATION_RECORD_SIZE
                    #
                    # If it's a time record, extract time on and time off,
                    # and set decimation to None.
                    #
                    else:
                        metadata = struct.unpack(TIME_FORMAT,
                            chunk[start_index : start_index + bytes_remaining])
                        metadata_list = list(metadata)
                        metadata_list.append(None)
                        bytes_remaining -= TIME_RECORD_SIZE

                    #
                    # Add remaining fields (serial number, number of records,
                    # POSIX timestamp) to the list, then turn it into a tuple
                    # and add it to the other fields.
                    #
                    metadata_list.append(serial_number)
                    metadata_list.append(records_processed)
                    metadata_list.append(sio_timestamp)
                    metadata = tuple(metadata_list)
                    fields.append(metadata)
                    metadata_found = True

                #
                # It's an error if we don't recognize any type of record.
                #
                else:
                    self.report_error(SampleException,
                        '%d bytes remaining at end of record' % bytes_remaining)
                    bytes_remaining = 0
                    particle_type = None

                if particle_type is not None:
                    particle_fields.append(fields)

        return particle_fields

    def report_error(self, exception, error_message):
        """
        This function reports an error condition by issuing a warning
        and raising an exception.
        Parameters:
          exception - type of exception to raise
          error_message - accompanying text
        """
        log.warn(error_message)
        raise exception(error_message)
