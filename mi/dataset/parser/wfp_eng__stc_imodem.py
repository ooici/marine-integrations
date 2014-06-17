#!/usr/bin/env python

"""
@package mi.dataset.parser.wfp_eng__stc_imodem_particles
@file marine-integrations/mi/dataset/parser/wfp_eng__stc_imodem_particles.py
@author Mark Worden
@brief Particles for the WFP_ENG__STC_IMODEM dataset driver
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

import copy
import ntplib
import struct

from mi.core.log import get_logger
log = get_logger()
from mi.core.exceptions import SampleException, DatasetParserException, UnexpectedDataException
from mi.dataset.parser.WFP_E_file_common import WfpEFileParser, StateKey, WFP_E_COASTAL_FLAGS_HEADER_MATCHER, \
    HEADER_BYTES, SAMPLE_BYTES, STATUS_BYTES, PROFILE_MATCHER
from mi.dataset.dataset_driver import DataSetDriverConfigKeys


class WfpEngStcImodemParser(WfpEFileParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        self._saved_header = None
        log.info(config)
        particle_classes_dict = config.get(DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT)
        self._start_data_particle_class = particle_classes_dict.get('start_data_particle_class')
        self._status_data_particle_class = particle_classes_dict.get('status_data_particle_class')
        self._engineering_data_particle_class = particle_classes_dict.get('engineering_data_particle_class')
        super(WfpEngStcImodemParser, self).__init__(config,
                                                    state,
                                                    stream_handle,
                                                    state_callback,
                                                    publish_callback,
                                                    *args, **kwargs)


    def set_state(self, state_obj):
        """
        initialize the state
        """
        log.trace("Attempting to set state to: %s", state_obj)
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not (StateKey.POSITION in state_obj):
            raise DatasetParserException("Invalid state keys")
        self._chunker.clean_all_chunks()
        self._record_buffer = []
        self._saved_header = None
        self._state = state_obj
        self._read_state = state_obj
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _parse_header(self):
        """
        Parse the start time of the profile and the sensor
        """
        # read the first bytes from the file
        header = self._stream_handle.read(HEADER_BYTES)

        match = WFP_E_COASTAL_FLAGS_HEADER_MATCHER.match(header)

        # parse the header
        if match is not None:

            # use the profile start time as the timestamp
            fields = struct.unpack('>II', match.group(2))
            timestamp = int(fields[1])
            self._timestamp = float(ntplib.system_to_ntp_time(timestamp))
            log.info(self._start_data_particle_class)
            sample = self._extract_sample(self._start_data_particle_class,
                                          None,
                                          header, self._timestamp)

            if sample:
                # create particle
                self._increment_state(HEADER_BYTES)
                log.debug("Extracting header %s with read_state: %s", sample, self._read_state)
                self._saved_header = (sample, copy.copy(self._read_state))
        else:
            raise SampleException("File header does not match header regex")

    def parse_record(self, record):
        """
        determine if this is a engineering or data record and parse
        """
        result_particle = []

        # Attempt to match on the profile status record
        match = PROFILE_MATCHER.match(record)

        if match is not None:
            # send to WFP_eng_profiler if WFP
            fields = struct.unpack('>ihhII', match.group(0))
            # use the profile stop time
            timestamp = int(fields[3])
            self._timestamp = float(ntplib.system_to_ntp_time(timestamp))
            log.info(self._status_data_particle_class)
            sample = self._extract_sample(self._status_data_particle_class, None,
                                          record, self._timestamp)
            self._increment_state(STATUS_BYTES)
        else:
            # The record data must be an engineering data record since it was not a profile status record

            # pull out the timestamp for this record
            fields = struct.unpack('>I', record[:4])
            timestamp = int(fields[0])
            self._timestamp = float(ntplib.system_to_ntp_time(timestamp))
            log.trace("Converting record timestamp %f to ntp timestamp %f", timestamp, self._timestamp)
            log.info(self._engineering_data_particle_class)
            sample = self._extract_sample(self._engineering_data_particle_class, None,
                                          record, self._timestamp)
            self._increment_state(SAMPLE_BYTES)

        if sample:
            # create particle
            log.trace("Extracting sample %s with read_state: %s", sample, self._read_state)
            result_particle = (sample, copy.copy(self._read_state))

        return result_particle

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """
        result_particles = []

        # header gets read in initialization, but need to send it back from parse_chunks
        if self._saved_header:
            result_particles.append(self._saved_header)
            self._saved_header = None

        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
        self.handle_non_data(non_data, non_end, start)

        while chunk is not None:
            result_particle = self.parse_record(chunk)
            if result_particle:
                result_particles.append(result_particle)

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
            self._exception_callback(UnexpectedDataException("Found %d bytes of un-expected non-data %s" %
                                                             (len(non_data), non_data)))
