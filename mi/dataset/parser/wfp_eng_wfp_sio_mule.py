#!/usr/bin/env python

"""
@package mi.dataset.parser.wfp_eng_wfp_sio_mule
@file marine-integrations/mi/dataset/parser/wfp_eng_wfp_sio_mule.py
@author Mark Worden
@brief Parser for the wfp_eng_wfp_sio_mule dataset driver
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

import re
import ntplib
import struct
import binascii

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, RecoverableSampleException
from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER
from mi.dataset.parser.WFP_E_file_common import WFP_E_GLOBAL_FLAGS_HEADER_REGEX, \
    WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_MATCHER, WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_BYTES
from mi.dataset.parser.WFP_E_file_common import STATUS_BYTES_AUGMENTED, \
    STATUS_BYTES, STATUS_START_MATCHER

# The regex for a WFP E data block.
DATA_REGEX = WFP_E_GLOBAL_FLAGS_HEADER_REGEX + '(.*)\x03'
DATA_MATCHER = re.compile(DATA_REGEX, flags=re.DOTALL)


class DataParticleType(BaseEnum):
    START_TIME = 'wfp_eng_wfp_sio_mule_start_time'
    STATUS = 'wfp_eng_wfp_sio_mule_status'
    ENGINEERING = 'wfp_eng_wfp_sio_mule_engineering'


class WfpEngWfpSioMuleParserDataStartTimeParticleKey(BaseEnum):
    CONTROLLER_TIMESTAMP = 'sio_controller_timestamp'
    WFP_SENSOR_START = 'wfp_sensor_start'
    WFP_PROFILE_START = 'wfp_profile_start'


class WfpEngWfpSioMuleParserDataStatusParticleKey(BaseEnum):
    CONTROLLER_TIMESTAMP = 'sio_controller_timestamp'
    WFP_INDICATOR = 'wfp_indicator'
    WFP_RAMP_STATUS = 'wfp_ramp_status'
    WFP_PROFILE_STATUS = 'wfp_profile_status'
    WFP_SENSOR_STOP = 'wfp_sensor_stop'
    WFP_PROFILE_STOP = 'wfp_profile_stop'
    WFP_DECIMATION_FACTOR = 'wfp_decimation_factor'


class WfpEngWfpSioMuleParserDataEngineeringParticleKey(BaseEnum):
    WFP_TIMESTAMP = 'wfp_timestamp'
    WFP_PROF_CURRENT = 'wfp_prof_current'
    WFP_PROF_VOLTAGE = 'wfp_prof_voltage'
    WFP_PROF_PRESSURE = 'wfp_prof_pressure'


class WfpEngWfpSioMuleParserDataStartTimeParticle(DataParticle):
    """
    Class for building the WfpEngWfpSioMuleParserDataStartTimeParticle
    """

    _data_particle_type = DataParticleType.START_TIME

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        result = []

        try:

            # Unpack the binary data content that includes:
            # - SIO controller timestamp 8 ASCII char string)
            # - sensor start time unsigned int
            # - profile start time unsigned int
            fields = struct.unpack_from('>8sII', self.raw_data)

            # Unpack the SIO controller timestamp in ASCII to unsigned int
            controller_timestamp = struct.unpack_from('>I', binascii.a2b_hex(fields[0]))[0]

            sensor_start_time = fields[1]
            profile_start_time = fields[2]

            result.append(self._encode_value(WfpEngWfpSioMuleParserDataStartTimeParticleKey.CONTROLLER_TIMESTAMP,
                                             controller_timestamp, int))
            result.append(self._encode_value(WfpEngWfpSioMuleParserDataStartTimeParticleKey.WFP_SENSOR_START,
                                             sensor_start_time, int))
            result.append(self._encode_value(WfpEngWfpSioMuleParserDataStartTimeParticleKey.WFP_PROFILE_START,
                                             profile_start_time, int))

        except (ValueError, TypeError, IndexError) as ex:
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]"
                                             % (ex, self.raw_data))

        return result


class WfpEngWfpSioMuleParserDataStatusParticle(DataParticle):
    """
    Class for building the WfpEngWfpSioMuleParserDataStatusParticle
    """

    _data_particle_type = DataParticleType.STATUS

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """

        result = []

        try:

            # Default the optional decimation factor to None
            decimation_factor = None

            # Unpack the binary data content that includes:
            # - SIO controller timestamp 8 ASCII char string)
            # - indicator int
            # - ramp status short
            # - profile status short
            # - profile stop time unsigned int
            # - sensor stop time unsigned int
            # - (optional) decimation factor
            if len(self.raw_data) == STATUS_BYTES_AUGMENTED:
                # Need to deal with the extra decimation factor
                fields = struct.unpack_from('>8sihhIIH', self.raw_data)

                # The last field is the unsigned int 16 decimation factor
                decimation_factor = fields[6]
            else:
                fields = struct.unpack_from('>8sihhII', self.raw_data)

            # Unpack the SIO controller timestamp in ASCII to unsigned int
            controller_timestamp = struct.unpack_from('>I', binascii.a2b_hex(fields[0]))[0]
            indicator = fields[1]
            ramp_status = fields[2]
            profile_status = fields[3]
            profile_stop_time = fields[4]
            sensor_stop_time = fields[5]

            result.append(self._encode_value(WfpEngWfpSioMuleParserDataStatusParticleKey.CONTROLLER_TIMESTAMP,
                                             controller_timestamp, int))
            result.append(self._encode_value(WfpEngWfpSioMuleParserDataStatusParticleKey.WFP_INDICATOR,
                                             indicator, int))
            result.append(self._encode_value(WfpEngWfpSioMuleParserDataStatusParticleKey.WFP_RAMP_STATUS,
                                             ramp_status, int))
            result.append(self._encode_value(WfpEngWfpSioMuleParserDataStatusParticleKey.WFP_PROFILE_STATUS,
                                             profile_status, int))
            result.append(self._encode_value(WfpEngWfpSioMuleParserDataStatusParticleKey.WFP_PROFILE_STOP,
                                             profile_stop_time, int))
            result.append(self._encode_value(WfpEngWfpSioMuleParserDataStatusParticleKey.WFP_SENSOR_STOP,
                                             sensor_stop_time, int))
            result.append({DataParticleKey.VALUE_ID: WfpEngWfpSioMuleParserDataStatusParticleKey.WFP_DECIMATION_FACTOR,
                           DataParticleKey.VALUE: decimation_factor})

        except (ValueError, TypeError, IndexError) as ex:
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]"
                                             % (ex, self.raw_data))

        return result


class WfpEngWfpSioMuleParserDataEngineeringParticle(DataParticle):
    """
    Class for building the WfpEngWfpSioMuleParserDataEngineeringParticle
    """

    _data_particle_type = DataParticleType.ENGINEERING
    
    def _build_parsed_values(self):
        """
        Take something in the binary data values and turn it into a
        particle with the appropriate tag.
        throws SampleException If there is a problem with sample creation
        """

        match = WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_MATCHER.match(self.raw_data)

        if not match:
            raise RecoverableSampleException(
                "WfpEngWfpSioMuleParserDataEngineeringParticle: No regex match of parsed sample data: [%s]",
                self.raw_data)

        try:
            # Let's first get the 32-bit unsigned int timestamp which should be in the first match group
            fields = struct.unpack_from('>I', match.group(1))
            wfp_timestamp = fields[0]

            # Now let's grab the global engineering data record match group
            # Should be 3 float 32-bit values
            fields = struct.unpack_from('>fff', match.group(2))

            current = fields[0]
            voltage = fields[1]
            pressure = fields[2]

            result = [self._encode_value(WfpEngWfpSioMuleParserDataEngineeringParticleKey.WFP_TIMESTAMP,
                                         wfp_timestamp, int),
                      self._encode_value(WfpEngWfpSioMuleParserDataEngineeringParticleKey.WFP_PROF_CURRENT,
                                         current, float),
                      self._encode_value(WfpEngWfpSioMuleParserDataEngineeringParticleKey.WFP_PROF_VOLTAGE,
                                         voltage, float),
                      self._encode_value(WfpEngWfpSioMuleParserDataEngineeringParticleKey.WFP_PROF_PRESSURE,
                                         pressure, float)]

        except (ValueError, TypeError, IndexError) as ex:
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]"
                                             % (ex, match.group(0)))

        return result


class WfpEngWfpSioMuleParser(SioMuleParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        super(WfpEngWfpSioMuleParser, self).__init__(config,
                                                     stream_handle,
                                                     state,
                                                     self.sieve_function,
                                                     state_callback,
                                                     publish_callback,
                                                     exception_callback,
                                                     *args,
                                                     **kwargs)

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

            header_match = SIO_HEADER_MATCHER.match(chunk)
            sample_count = 0

            # Check to see if we are dealing with a wfp_eng SIO chunk
            if header_match.group(1) == 'WE':

                data_match = DATA_MATCHER.match(chunk[len(header_match.group(0)):])

                controller_timestamp = header_match.group(3)

                if data_match:

                    sensor_profile_start_time_data = data_match.group(2)

                    if sensor_profile_start_time_data:

                        # Need to unpack the sensor profile start time timestamp
                        fields_prof = struct.unpack_from('>I', sensor_profile_start_time_data[4:])
                        timestamp = fields_prof[0]

                        sample = self._extract_sample(WfpEngWfpSioMuleParserDataStartTimeParticle, None,
                                                      controller_timestamp +
                                                      sensor_profile_start_time_data,
                                                      float(ntplib.system_to_ntp_time(timestamp)))
                        if sample:
                            log.debug("Sample found: %s", sample)
                            # create particle
                            result_particles.append(sample)
                            sample_count += 1

                    profile_eng_data = data_match.group(3)

                    # Start from the end of the chunk and working backwards
                    parse_end_point = len(profile_eng_data)

                    # We are going to go through the file data in reverse order since we have a
                    # variable length sample record that could have a decimation factor.
                    # While we do not hit the beginning of the file contents, continue
                    while parse_end_point > 0:

                        # Create the different start indices for the three different scenarios
                        start_index_augmented = parse_end_point-STATUS_BYTES_AUGMENTED
                        start_index_normal = parse_end_point-STATUS_BYTES
                        global_recovered_eng_rec_index = parse_end_point-WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_BYTES

                        # Check for an an augmented status first
                        if start_index_augmented >= 0 and \
                                STATUS_START_MATCHER.match(profile_eng_data[start_index_augmented:parse_end_point]):
                            log.debug("Found OffloadProfileData with decimation factor")

                            fields_prof = struct.unpack_from('>I', profile_eng_data[start_index_augmented+8:])
                            timestamp = fields_prof[0]

                            sample = self._extract_sample(WfpEngWfpSioMuleParserDataStatusParticle, None,
                                                          controller_timestamp +
                                                          profile_eng_data[start_index_augmented:parse_end_point],
                                                          float(ntplib.system_to_ntp_time(timestamp)))

                            # Set the new end point
                            parse_end_point = start_index_augmented

                        # Check for a normal status
                        elif start_index_normal >= 0 and \
                                STATUS_START_MATCHER.match(profile_eng_data[start_index_normal:parse_end_point]):
                            log.debug("Found OffloadProfileData without decimation factor")

                            fields_prof = struct.unpack_from('>I', profile_eng_data[start_index_normal+8:])
                            timestamp = fields_prof[0]

                            sample = self._extract_sample(WfpEngWfpSioMuleParserDataStatusParticle, None,
                                                          controller_timestamp +
                                                          profile_eng_data[start_index_normal:parse_end_point],
                                                          float(ntplib.system_to_ntp_time(timestamp)))

                            parse_end_point = start_index_normal

                        # If neither, we are dealing with a global wfp e recovered engineering data record,
                        # so we will save the start and end points
                        elif global_recovered_eng_rec_index >= 0:
                            log.debug("Found OffloadEngineeringData")

                            fields_prof = struct.unpack_from('>I', profile_eng_data[global_recovered_eng_rec_index:])
                            timestamp = fields_prof[0]

                            sample = self._extract_sample(WfpEngWfpSioMuleParserDataEngineeringParticle, None,
                                                          profile_eng_data[
                                                          global_recovered_eng_rec_index:parse_end_point],
                                                          float(ntplib.system_to_ntp_time(timestamp)))

                            # Set the new end point
                            parse_end_point = global_recovered_eng_rec_index

                        # We must not have a good file, log some debug info for now
                        else:
                            log.debug("start_index_augmented %d", start_index_augmented)
                            log.debug("start_index_normal %d", start_index_normal)
                            log.debug("global_recovered_eng_rec_index %d", global_recovered_eng_rec_index)
                            self._exception_callback(SampleException("Data invalid"))

                        if sample:
                            log.debug("Sample found: %s", sample)
                            # create particle
                            result_particles.append(sample)
                            sample_count += 1

                else:
                    self._exception_callback(SampleException("Unexpected data"))

            # Important:  We must set the sample count for every chunk
            self._chunk_sample_count.append(sample_count)

            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

        return result_particles
