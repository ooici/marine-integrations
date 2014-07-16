#!/usr/bin/env python

"""
@package mi.dataset.parser.vel3d_l_wfp
@file marine-integrations/mi/dataset/parser/vel3d_l_wfp.py
@author Steve Myerson (Raytheon)
@brief Parser for the vel3d_l_wfp dataset driver"
This file contains classes for both the vel3d_l_wfp parser (recovered data)
and the vel3d_l_wfp_sio_mule parser (telemetered data wrapped in SIO blocks).
Release notes:

Initial Release
"""

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

import calendar
import copy
import struct

from mi.core.log import get_logger; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import \
    DatasetParserException, \
    SampleException, \
    UnexpectedDataException

from mi.dataset.dataset_parser import \
    Parser, \
    BufferLoadingParser

from mi.dataset.parser.sio_mule_common import \
    SioMuleParser, \
    SIO_HEADER_MATCHER, \
    SIO_HEADER_GROUP_ID, \
    SIO_HEADER_GROUP_TIMESTAMP


ID_VEL3D_L_WFP_SIO_MULE = 'WA'    # The type of instrument for telemetered data

#
# File format (this does not include the SIO header
# which is applicable to telemetered data only):
# Data bytes (4 bytes) - Field is used for Recovered, ignored for Telemetered
# FSI Header (279 bytes)
# FSI Record (47 bytes * N instances)
# Sensor start time (4 bytes)
# Sensor stop time (4 bytes)
# Decimation (2 bytes, optional for Telemetered, N/A for Recovered)
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
# Instrument Particles are the same for both recovered and telemetered data.
#
INDEX_PARTICLE_KEY = 0    # Index into the xxx_PARTICLE_KEYS tables
INDEX_VALUE_TYPE = 1      # Index into the xxx_PARTICLE_KEYS tables

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

SIO_METADATA_PARTICLE_KEYS = \
[
    [None,                           None],  # Metadata timestamp handled separately
    ['vel3d_l_time_on',              int],
    ['vel3d_l_time_off',             int],
    ['vel3d_l_serial_number',        int],
    ['vel3d_l_number_of_records',    int],
    ['vel3d_l_decimation_factor',    int],
    ['vel3d_l_controller_timestamp', int]
]

WFP_METADATA_PARTICLE_KEYS = \
[
    [None,                        None],    # Metadata timestamp handled separately
    ['vel3d_l_time_on',           int],
    ['vel3d_l_time_off',          int],
    ['vel3d_l_serial_number',     int],
    ['vel3d_l_number_of_records', int]
]

DATE_TIME_ARRAY = 'vel3d_l_date_time_array'  # This one needs to be special-cased
DATE_TIME_SIZE = 6                     # 6 bytes for the output date time field

DECIMATION_RECORD_SIZE = 10  # bytes in time fields plus decimation field
DECIMATION_FORMAT = '>2IH'   # 2 uint32, 1 uint16
TIME_RECORD_SIZE = 8         # bytes in time fields
TIME_FORMAT = '>2I'          # 2 uint32
FIELD_METADATA_TIMESTAMP = 0
FIELD_TIME_ON = 1
FIELD_TIME_OFF = 2
FIELD_SERIAL_NUMBER = 3
FIELD_NUMBER_OF_RECORDS = 4
FIELD_DECIMATION = 5
FIELD_CONTROLLER_TIMESTAMP = 6

PARTICLE_TYPE_SIO_INSTRUMENT = 1
PARTICLE_TYPE_SIO_METADATA = 2
PARTICLE_TYPE_WFP_INSTRUMENT = 3
PARTICLE_TYPE_WFP_METADATA = 4


class Vel3dLWfpStateKey(BaseEnum):
    POSITION = 'position'                  # holds the file position
    PARTICLE_NUMBER = 'particle_number'    # particle number of N


class Vel3dLWfpDataParticleType(BaseEnum):
    """
    These are the names of the output particle streams as specified in the IDD.
    """
    SIO_INSTRUMENT_PARTICLE = 'vel3d_l_wfp_instrument'
    SIO_METADATA_PARTICLE = 'vel3d_l_wfp_sio_mule_metadata'
    WFP_INSTRUMENT_PARTICLE = 'vel3d_l_wfp_instrument_recovered'
    WFP_METADATA_PARTICLE = 'vel3d_l_wfp_metadata_recovered'


class Vel3dLWfpInstrumentDataParticle(DataParticle):
    """
    Generic class for generating vel3d_l_wfp instrument particles.
    This class is for both recovered and telemetered data.
    The output particle streams for vel3d_l instrument data have different
    names, but the contents of the 2 streams are identical.
    """
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into an array of
        dictionaries defining the data in the particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        Parameters:
            particle_key_table - list of particle keywords to be matched against the
                raw_data which has the parsed fields in the same order as the keys
        Returns:
            list of instrument particle values
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
                # When generating the date time array field in the instrument particle,
                # use these same values to generate the timestamp for this particle.
                #
                hour = fields[field_index]
                minute = fields[field_index + 1]
                second = fields[field_index + 2]
                month = fields[field_index + 3]
                day = fields[field_index + 4]
                year = fields[field_index + 5]

                timestamp = (year, month, day, hour, minute, second, 0, 0, 0)
                elapsed_seconds = calendar.timegm(timestamp)
                self.set_internal_timestamp(unix_time=elapsed_seconds)

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


class Vel3dLWfpInstrumentParticle(Vel3dLWfpInstrumentDataParticle):
    """
    Class for generating vel3d_l_wfp instrument telemetered particles.
    All processing is handled by the parent class as long as the
    data particle type is set correctly.
    """

    _data_particle_type = Vel3dLWfpDataParticleType.SIO_INSTRUMENT_PARTICLE


class Vel3dLWfpInstrumentRecoveredParticle(Vel3dLWfpInstrumentDataParticle):
    """
    Class for generating vel3d_l_wfp instrument recovered particles.
    All processing is handled by the parent class as long as the
    data particle type is set correctly.
    """

    _data_particle_type = Vel3dLWfpDataParticleType.WFP_INSTRUMENT_PARTICLE


class Vel3dLMetadataParticle(DataParticle):
    """
    Generic class for generating vel3d_l metadata particles,
    both recovered and telemetered.
    """

    def generate_metadata_particle(self, particle_key_table):
        """
        Take something in the data format and turn it into an array of
        dictionaries defining the data in the particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        Parameters:
            particle_key_table - list of particle keywords to be matched against the
                raw_data which has the parsed fields in the same order as the keys
        """
        #
        # Generate a Metadata data particle.
        # Note that raw_data already contains the individual fields
        # extracted and unpacked from the metadata record.
        # It is assumed that the individual fields are in the correct order
        # corresponding to the table of keys.
        #
        particle = []
        field_index = 0
        fields = self.raw_data

        #
        # The timestamp for the Metadata particle varies depending on whether
        # this is recovered or telemetered data.
        # This determination is made when the input file is parsed.
        # Here, whatever value is sent is used as the timestamp.
        #
        self.set_internal_timestamp(unix_time=fields[FIELD_METADATA_TIMESTAMP])

        #
        # Extract the metadata particle fields from the parsed values.
        #
        for x in range(0, len(particle_key_table)):
            key = particle_key_table[x][INDEX_PARTICLE_KEY]
            if key is not None:

                #
                # There is a bug in encode_value in the parent class.
                # If the value is 'None', encode_value chokes.
                # Apparently this bug is not important enough to fix in the parent
                # class, so it is incumbent on each child class to generate a
                # work-around.
                #
                if fields[field_index] is None:
                    particle.append({DataParticleKey.VALUE_ID: key,
                                     DataParticleKey.VALUE: None})
                else:
                    particle_value = self._encode_value(key, fields[field_index],
                        particle_key_table[x][INDEX_VALUE_TYPE])
                    particle.append(particle_value)

            field_index += 1

        return particle


class Vel3dLWfpMetadataRecoveredParticle(Vel3dLMetadataParticle):
    """
    Class for generating vel3d_l_wfp metadata recovered particles.
    """

    _data_particle_type = Vel3dLWfpDataParticleType.WFP_METADATA_PARTICLE

    def _build_parsed_values(self):
        """
        Call the generic generate_metadata_particle function to generate the
        WFP Metadata particle.
        """
        return self.generate_metadata_particle(WFP_METADATA_PARTICLE_KEYS)


class Vel3dLWfpSioMuleMetadataParticle(Vel3dLMetadataParticle):
    """
    Class for generating vel3d_l_wfp_sio_mule metadata particles.
    """

    _data_particle_type = Vel3dLWfpDataParticleType.SIO_METADATA_PARTICLE

    def _build_parsed_values(self):
        """
        Call the generic generate_metadata_particle function to generate the
        SIO Mule Metadata particle.
        """
        return self.generate_metadata_particle(SIO_METADATA_PARTICLE_KEYS)


class Vel3dLParser(Parser):
    """
    This class contains functions that are common to both the Vel3dLWfp and
    Vel3dLWfpSioMule parsers.
    """
    def generate_samples(self, fields):
        """
        Given a list of groups of particle fields, generate particles for each group.
        Parameters:
            fields - (particle type, (parsed values to be put into output particles))
        Returns:
            sample_count - number of samples found
            samples - list of samples found
        """
        samples = []
        sample_count = 0

        if len(fields) > 0:
            for x in range(0, len(fields)):
                particle_type = fields[x][0]

                if particle_type == PARTICLE_TYPE_SIO_INSTRUMENT:
                    particle_class = Vel3dLWfpInstrumentParticle
                elif particle_type == PARTICLE_TYPE_WFP_INSTRUMENT:
                    particle_class = Vel3dLWfpInstrumentRecoveredParticle
                elif particle_type == PARTICLE_TYPE_SIO_METADATA:
                    particle_class = Vel3dLWfpSioMuleMetadataParticle
                else:
                    particle_class = Vel3dLWfpMetadataRecoveredParticle

                #
                # Since the record has already been parsed,
                # the individual fields are passed to be stored and used
                # when generating the particle key/value pairs.
                # Timestamp is None since the particle generation handles that.
                #
                sample = self._extract_sample(particle_class, None,
                                              fields[x][1], None)
                if sample:
                    #
                    # Add the particle to the list of particles
                    #
                    samples.append(sample)
                    sample_count += 1

        return sample_count, samples

    def parse_vel3d_data(self, instrument_particle_type, metadata_particle_type,
                         chunk, time_stamp=None):
        """
        This function parses the Vel3d data, including the FSI Header,
        FSI Records, and Metadata.
        Parameters:
            instrument_particle_type - Which instrument particle is being generated.
            metadata_particle_type - Which metadata particle is being generated.
            chunk - Vel3d data, starting with the data_bytes field.
            time_stamp (optional) - specified for SIO Mule data only.
        Returns:
            particle_fields - The fields resulting from parsing the FSI Header,
                FSI records, and Metadata.
        """
        particle_fields = []    # Initialize return parameter to empty

        #
        # Skip past the Data Bytes field to get to the start of the FSI Header.
        # We don't care about the Data Bytes field.
        #
        start_index = DATA_BYTES_SIZE

        #
        # Extract the little endian 32-bit serial number from the FSI Header.
        #
        serial_number_start = start_index + FSI_HEADER_SERIAL_NUMBER_OFFSET
        serial_number = struct.unpack('<I',
            chunk[serial_number_start :
                  serial_number_start + FSI_HEADER_SERIAL_NUMBER_SIZE])[0]

        #
        # Skip past the FSI Header to get to the first FSI record.
        #
        start_index += FSI_HEADER_SIZE

        #
        # Calculate the number of bytes remaining to be processed.
        #
        bytes_remaining = len(chunk) - start_index

        #
        # Calculate the number of FSI records expected.
        #
        records_expected = bytes_remaining / FSI_RECORD_SIZE

        #
        # As long as there is more data in the chunk.
        #
        records_processed = 0
        metadata_found = False
        while bytes_remaining > 0:
            fields = []

            #
            # If there are enough bytes to comprise an FSI record and
            # we haven't yet processed the expected number of FSI records,
            # extract the fields from the FSI record.
            #
            if bytes_remaining >= FSI_RECORD_SIZE and \
               records_processed != records_expected:
                particle_type = instrument_particle_type
                fields.append(particle_type)

                fields.append(struct.unpack(FSI_RECORD_FORMAT,
                    chunk[start_index : start_index + FSI_RECORD_SIZE]))
                bytes_remaining -= FSI_RECORD_SIZE
                start_index += FSI_RECORD_SIZE
                records_processed += 1

            #
            # Once all the FSI records have been processed,
            # check for a decimation or time record (Metadata).
            # If there are enough bytes to comprise a decimation record
            # or a time record, extract the fields from the record.
            #
            elif records_processed == records_expected and \
                not metadata_found and \
                (bytes_remaining == DECIMATION_RECORD_SIZE or
                bytes_remaining == TIME_RECORD_SIZE):

                #
                # If it's a decimation record, extract time on, time off
                # and the decimation factor.
                #
                particle_type = metadata_particle_type
                fields.append(particle_type)

                if bytes_remaining == DECIMATION_RECORD_SIZE:
                    (time_on, time_off, decimation) = struct.unpack(DECIMATION_FORMAT,
                        chunk[start_index : start_index + bytes_remaining])
                    bytes_remaining -= DECIMATION_RECORD_SIZE

                #
                # If it's a time record, extract time on and time off,
                # and set decimation to None.
                #
                else:
                    (time_on, time_off) = struct.unpack(TIME_FORMAT,
                        chunk[start_index : start_index + bytes_remaining])
                    decimation = None
                    bytes_remaining -= TIME_RECORD_SIZE

                #
                # Create the metadata fields depending on which metadata
                # particle type is being created.
                # The fields must be in the same order as the Particle Keys tables.
                #
                if particle_type == PARTICLE_TYPE_SIO_METADATA:
                    metadata = (time_stamp, time_on, time_off, serial_number,
                                records_processed, decimation, time_stamp)
                else:
                    metadata = (time_off, time_on, time_off, serial_number,
                                records_processed)

                fields.append(metadata)
                metadata_found = True

            #
            # It's an error if we don't recognize any type of record
            # of if we've processed everything we expected to and there's
            # still more bytes remaining.
            #
            else:
                self.report_error(SampleException, 'Improperly formatted input file')
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


class Vel3dLWfpParser(BufferLoadingParser, Vel3dLParser):

    def __init__(self, config, state, file_handle,
                 state_callback, publish_callback, exception_callback):
        """
        @param config The configuration parameters to feed into the parser
        @param state The location in the file to start parsing from.
           This reflects what has already been published.
        @param file_handle An already open file-like file handle
        @param state_callback The callback method from the agent driver
           (ultimately the agent) to call back when a state needs to be
           updated
        @param publish_callback The callback from the agent driver (and
           ultimately from the agent) where we send our sample particle to
           be published into ION
        @param exception_callback The callback from the agent driver to
           send an exception to
        """

        super(Vel3dLWfpParser, self).__init__(config, file_handle, state,
            self.sieve_function, state_callback, publish_callback, exception_callback)

        self.input_file = file_handle
        self._read_state = {
            Vel3dLWfpStateKey.POSITION: 0,
            Vel3dLWfpStateKey.PARTICLE_NUMBER: 0
        }

        if state is not None:
            log.debug('XXX VEL state %s', state)
            self.set_state(state)

    def handle_non_data(self, non_data, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # Handle non-data here by calling the exception callback.
        if non_data is not None and non_end <= start:
            # increment the state
            self._increment_position(len(non_data))
            # use the _exception_callback
            self._exception_callback(UnexpectedDataException(
                "Found %d bytes of un-expected non-data %s" % (len(non_data), non_data)))

    def _increment_position(self, bytes_read):
        """
        Increment the parser position
        @param bytes_read The number of bytes just read
        """
        self._read_state[Vel3dLWfpStateKey.POSITION] += bytes_read

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state.
        """
        result_particles = []
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
        self.handle_non_data(non_data, non_end, start)

        while chunk is not None:
            fields = self.parse_vel3d_data(PARTICLE_TYPE_WFP_INSTRUMENT,
                                           PARTICLE_TYPE_WFP_METADATA,
                                           chunk)

            #
            # Generate the particles for this chunk.
            # Add them to the return list of particles.
            # Increment the state (position within the file) for the last particle.
            # The first N-1 particles are tagged with the previous file position
            # and a PARTICLE_NUMBER 1 to N.
            # The Nth particle is tagged with with current file position
            # and a PARTICLE_NUMBER of 0.
            #
            (sample_count, particles) = self.generate_samples(fields)
            for x in range(self._read_state[Vel3dLWfpStateKey.PARTICLE_NUMBER],
                           sample_count - 1):
                self._read_state[Vel3dLWfpStateKey.PARTICLE_NUMBER] += 1
                result_particles.append((particles[x], copy.copy(self._read_state)))

            self._increment_position(len(chunk))
            self._read_state[Vel3dLWfpStateKey.PARTICLE_NUMBER] = 0
            result_particles.append((particles[sample_count - 1],
                                     copy.copy(self._read_state)))

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            self.handle_non_data(non_data, non_end, start)

        return result_particles

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to.
        @throws DatasetParserException if there is a bad state structure
        """
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")

        if not (Vel3dLWfpStateKey.POSITION in state_obj):
            raise DatasetParserException("State key %s missing" %
                                         Vel3dLWfpStateKey.POSITION)

        if not (Vel3dLWfpStateKey.PARTICLE_NUMBER in state_obj):
            raise DatasetParserException("State key %s missing" %
                                         Vel3dLWfpStateKey.PARTICLE_NUMBER)

        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        self.input_file.seek(state_obj[Vel3dLWfpStateKey.POSITION])

    def sieve_function(self, input_buffer):
        """
        Sort through the input buffer looking for Recovered data records.
        Arguments:
            input_buffer - the contents of the input stream
        Returns:
            A list of start,end tuples
        """

        indices_list = []    # initialize the return list to empty

        start_index = 0
        while start_index < len(input_buffer):
            #
            # Extract the number of data_bytes.
            # This is the number of bytes in the FSI Header and FSI records,
            # and excludes the data_bytes field and the time fields.
            #
            data_bytes = struct.unpack('>I',
                input_buffer[start_index : start_index + DATA_BYTES_SIZE])[0]

            #
            # Calculate the end of packet.
            # This includes the data_bytes field, the FSI Header,
            # some number of FSI records, and the 2 time fields.
            #
            end_index = start_index + DATA_BYTES_SIZE + data_bytes + TIME_RECORD_SIZE

            #
            # If the input buffer has enough bytes for the entire packet,
            # add the start,end pair to the list of indices.
            # If not enough room, we're done for now.
            #
            if end_index <= len(input_buffer):
                indices_list.append((start_index, end_index))
                start_index = end_index
            else:
                break

        return indices_list


class Vel3dLWfpSioMuleParser(SioMuleParser, Vel3dLParser):

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
            self.sieve_function, state_callback, publish_callback, exception_callback)

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """
        result_particles = []
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

        while chunk is not None:
            #
            # Verify that the Instrument ID is the one that we want.
            #
            header = SIO_HEADER_MATCHER.match(chunk)
            if header.group(SIO_HEADER_GROUP_ID) == ID_VEL3D_L_WFP_SIO_MULE:
                #
                # Extract the POSIX timestamp from the SIO Header.
                #
                sio_timestamp = int(header.group(SIO_HEADER_GROUP_TIMESTAMP), 16)

                #
                # Process the remaining Vel3d data, starting from the end of the
                # SIO Header, but not including the trailing 0x03.
                #
                fields = self.parse_vel3d_data(PARTICLE_TYPE_SIO_INSTRUMENT,
                    PARTICLE_TYPE_SIO_METADATA,
                    chunk[header.end(0) : -1],
                    time_stamp=sio_timestamp)

                #
                # Generate the particles for this SIO block.
                # Add them to the return list of particles.
                #
                (samples, particles) = self.generate_samples(fields)
                for x in range(0, samples):
                    result_particles.append(particles[x])

            #
            # Not our instrument, but still must indicate that no samples were found.
            #
            else:
                samples = 0

            # keep track of how many samples were found in this chunk
            self._chunk_sample_count.append(samples)

            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

        return result_particles
