#!/usr/bin/env python

"""
@package mi.dataset.parser.dosta_ln_wfp
@file marine-integrations/mi/dataset/parser/dosta_ln_wfp.py
@author Mark Worden
@brief Parser for the dosta_ln_wfp dataset driver
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

import copy
import gevent
import ntplib
import struct
import binascii

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.exceptions import SampleException, UnexpectedDataException
from mi.dataset.parser.WFP_E_file_common import WfpEFileParser, HEADER_BYTES, STATUS_BYTES_AUGMENTED, \
    STATUS_BYTES, STATUS_START_MATCHER, WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_MATCHER, \
    WFP_E_GLOBAL_FLAGS_HEADER_MATCHER, WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_BYTES


class DataParticleType(BaseEnum):
    INSTRUMENT = 'dosta_ln_wfp_instrument_recovered'


class DostaLnWfpInstrumentParserDataParticleKey(BaseEnum):
    ESTIMATED_OXYGEN_CONCENTRATION = 'estimated_oxygen_concentration'
    OPTODE_TEMPERATURE = 'optode_temperature'
    WFP_TIMESTAMP = 'wfp_timestamp'


class DostaLnWfpInstrumentParserDataParticle(DataParticle):
    """
    Class to build parsed values for the dosta_ln_wfp_instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        match = WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_MATCHER.match(self.raw_data)

        if not match:
            raise SampleException("DostaLnWfpInstrumentParserDataParticle: No regex match of parsed sample data: [0x%s]",
                                  binascii.b2a_hex(self.raw_data))

        try:
            # Let's first get the 32-bit unsigned int timestamp which should be in the first match group
            fields_prof = struct.unpack_from('>I', match.group(1))
            wfp_timestamp = fields_prof[0]

            # Now let's grab the global engineering data record match group
            # Should be 5 float 32-bit values followed by 3 unsigned int 16-bit values
            fields_prof = struct.unpack_from('>fffffHHH', match.group(2))
            # the optode_oxygen field should be the 4th value
            estimated_oxygen_concentration = fields_prof[3]
            # the optode_oxygen field should be the 5th value
            optode_temperature = fields_prof[4]

        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [0x%s]"
                                  % (ex, binascii.b2a_hex(match.group(0))))

        result = [self._encode_value(DostaLnWfpInstrumentParserDataParticleKey.ESTIMATED_OXYGEN_CONCENTRATION,
                                     estimated_oxygen_concentration, float),
                  self._encode_value(DostaLnWfpInstrumentParserDataParticleKey.OPTODE_TEMPERATURE,
                                     optode_temperature, float),
                  self._encode_value(DostaLnWfpInstrumentParserDataParticleKey.WFP_TIMESTAMP,
                                     wfp_timestamp, int)]
        return result


class DostaLnWfpParser(WfpEFileParser):
    """
    Class used to parse the dosta_ln_wfp recovered data stream
    """

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        self._saved_header = None
        super(DostaLnWfpParser, self).__init__(config,
                                               state,
                                               stream_handle,
                                               state_callback,
                                               publish_callback,
                                               *args, **kwargs)

    def _parse_header(self):
        """
        This method ensures the header data matches the wfp e global flags
        """
        # read the first bytes from the file
        header = self._stream_handle.read(HEADER_BYTES)
        match = WFP_E_GLOBAL_FLAGS_HEADER_MATCHER.match(header)
        if not match:
            raise SampleException("File header does not match the header regex")

        self._saved_header = header

        # update the state to show we have read the header
        self._increment_state(HEADER_BYTES)

    def get_block(self):
        """
        This function overwrites the get_block function in dataset_parser.py
        to  read the entire file rather than break it into chunks.
        Returns:
          The length of data retrieved.
        An EOFError is raised when the end of the file is reached.
        """
        # Read in data in blocks so as to not tie up the CPU.
        block_size = 1024
        eof = False
        data = ''
        while not eof:
            next_block = self._stream_handle.read(block_size)
            if next_block:
                data = data + next_block
                gevent.sleep(0)
            else:
                eof = True

        if data != '':
            self._chunker.add_chunk(data, self._timestamp)
            self.file_complete = True
            return len(data)
        else:  # EOF
            self.file_complete = True
            raise EOFError

    def sieve_function(self, raw_data):
        """
        This method sorts through the raw data to identify new blocks of data that need
        processing.  This is needed instead of a regex because blocks are identified by
        position in this binary file.
        """
        form_list = []
        raw_data_len = len(raw_data)

        # Starting from the end of the buffer and working backwards
        parse_end_point = raw_data_len

        # We are going to go through the file data in reverse order since we have a
        # variable length status indicator field.
        # While we do not hit the beginning of the file contents, continue
        while parse_end_point > 0:

            # Create the different start indices for the three different scenarios
            raw_data_start_index_augmented = parse_end_point-STATUS_BYTES_AUGMENTED
            raw_data_start_index_normal = parse_end_point-STATUS_BYTES
            global_recovered_eng_rec_index = parse_end_point-WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_BYTES

            # Check for an an augmented status first
            if raw_data_start_index_augmented >= 0 and \
                    STATUS_START_MATCHER.match(raw_data[raw_data_start_index_augmented:parse_end_point]):
                log.trace("Found OffloadProfileData with decimation factor")
                parse_end_point = raw_data_start_index_augmented

            # Check for a normal status
            elif raw_data_start_index_normal >= 0 and \
                    STATUS_START_MATCHER.match(raw_data[raw_data_start_index_normal:parse_end_point]):
                log.trace("Found OffloadProfileData without decimation factor")
                parse_end_point = raw_data_start_index_normal

            # If neither, we are dealing with a global wfp e recovered engineering data record,
            # so we will save the start and end points
            elif global_recovered_eng_rec_index >= 0:
                log.trace("Found OffloadEngineeringData")
                form_list.append((global_recovered_eng_rec_index, parse_end_point))
                parse_end_point = global_recovered_eng_rec_index

            # We must not have a good file, log some debug info for now
            else:
                log.debug("raw_data_start_index_augmented %d", raw_data_start_index_augmented)
                log.debug("raw_data_start_index_normal %d", raw_data_start_index_normal)
                log.debug("global_recovered_eng_rec_index %d", global_recovered_eng_rec_index)
                log.debug("bad file or bad position?")
                raise SampleException("File size is invalid or improper positioning")

        return_list = form_list[::-1]

        return return_list

    def parse_chunks(self):
        """
        This method parses out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """
        log.debug("parse_chunks")
        result_particles = []
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
        self.handle_non_data(non_data, non_end, start)

        while chunk is not None:

            data_match = WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_MATCHER.match(chunk)

            if data_match:

                # Let's first get the 32-bit unsigned int timestamp which should be in the first match group
                fields_prof = struct.unpack_from('>I', data_match.group(1))
                timestamp = fields_prof[0]
                self._timestamp = float(ntplib.system_to_ntp_time(timestamp))

                # particle-ize the data block received, return the record
                sample = self._extract_sample(self._particle_class,
                                              None,
                                              chunk,
                                              self._timestamp)
                if sample:
                    # create particle
                    log.trace("Extracting sample chunk 0x%s with read_state: %s", binascii.b2a_hex(chunk),
                              self._read_state)
                    self._increment_state(len(chunk))
                    result_particles.append((sample, copy.copy(self._read_state)))

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            self.handle_non_data(non_data, non_end, start)

        return result_particles

    def handle_non_data(self, non_data, non_end, start):
        """
        This method handles any non-data that is found in the file
        """
        # if non-data is expected, handle it here, otherwise it is an error
        if non_data is not None and non_end <= start:
            # if this non-data is an error, send an UnexpectedDataException and increment the state
            self._increment_state(len(non_data))
            # if non-data is a fatal error, directly call the exception, if it is not use the _exception_callback
            self._exception_callback(UnexpectedDataException("Found %d bytes of un-expected non-data 0x%s" %
                                                             (len(non_data), binascii.b2a_hex(non_data))))
