#!/usr/bin/env python

"""
@package mi.dataset.parser.optaa_ac_mmp_cds
@file marine-integrations/mi/dataset/parser/optaa_ac_mmp_cds.py
@author Mark Worden
@brief Parser for the optaa_ac_mmp_cds dataset driver
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

import struct

from mi.core.log import get_logger

log = get_logger()
from mi.core.common import BaseEnum
from mi.dataset.parser.mmp_cds_base import MmpCdsParserDataParticle, MmpCdsParser


class DataParticleType(BaseEnum):
    INSTRUMENT = 'optaa_ac_mmp_cds_instrument'


class OptaaAcMmpCdsParserDataParticleKey(BaseEnum):
    PACKET_TYPE = 'packet_type'
    METER_TYPE = 'meter_type'
    SERIAL_NUMBER = 'serial_number'
    A_REFERENCE_DARK_COUNTS = 'a_reference_dark_counts'
    PRESSURE_COUNTS = 'pressure_counts'
    A_SIGNAL_DARK_COUNTS = 'a_signal_dark_counts'
    EXTERNAL_TEMP_RAW = 'external_temp_raw'
    INTERNAL_TEMP_RAW = 'internal_temp_raw'
    C_REFERENCE_DARK_COUNTS = 'c_reference_dark_counts'
    C_SIGNAL_DARK_COUNTS = 'c_signal_dark_counts'
    ELAPSED_RUN_TIME = 'elapsed_run_time'
    NUM_WAVELENGTHS = 'num_wavelengths'
    C_REFERENCE_COUNTS = 'c_reference_counts'
    A_REFERENCE_COUNTS = 'a_reference_counts'
    C_SIGNAL_COUNTS = 'c_signal_counts'
    A_SIGNAL_COUNTS = 'a_signal_counts'


class EncodingParams:

    def __init__(self, key, unpack_code, unpack_from_offset, encode_type):

        self.key = key
        self.unpack_code = unpack_code
        self.unpack_from_offset = unpack_from_offset
        self.encode_type = encode_type


# The following are byte offsets used to access items within the binary data 
# processed by the OptaaAcMmpCdsParserDataParticle _get_mmp_cds_subclass_particle_params
PACKET_TYPE_DATA_OFFSET = 0
METER_TYPE_DATA_OFFSET = 2
SERIAL_NUMBER_DATA_OFFSET = 3
A_REFERENCE_DARK_COUNTS_DATA_OFFSET = 6
PRESSURE_COUNTS_DATA_OFFSET = 8
A_SIGNAL_DARK_COUNTS_DATA_OFFSET = 10
EXTERNAL_TEMP_RAW_DATA_OFFSET = 12
INTERNAL_TEMP_RAW_DATA_OFFSET = 14
C_REFERENCE_DARK_COUNTS_DATA_OFFSET = 16
C_SIGNAL_DARK_COUNTS_DATA_OFFSET = 18
ELAPSED_RUN_TIME_DATA_OFFSET = 20
NUM_WAVELENGTHS_DATA_OFFSET = 25
RAW_REF_AND_SIGNAL_COUNTS_BASE_OFFSET = 26

ENCODING_PARAMS = [
    EncodingParams(OptaaAcMmpCdsParserDataParticleKey.PACKET_TYPE, 'B', PACKET_TYPE_DATA_OFFSET, int),
    EncodingParams(OptaaAcMmpCdsParserDataParticleKey.METER_TYPE, 'B', METER_TYPE_DATA_OFFSET, int),
    EncodingParams(OptaaAcMmpCdsParserDataParticleKey.A_REFERENCE_DARK_COUNTS, 'H',
                   A_REFERENCE_DARK_COUNTS_DATA_OFFSET, int),
    EncodingParams(OptaaAcMmpCdsParserDataParticleKey.PRESSURE_COUNTS, 'H', PRESSURE_COUNTS_DATA_OFFSET, int),
    EncodingParams(OptaaAcMmpCdsParserDataParticleKey.A_SIGNAL_DARK_COUNTS, 'H',
                   A_SIGNAL_DARK_COUNTS_DATA_OFFSET, int),
    EncodingParams(OptaaAcMmpCdsParserDataParticleKey.EXTERNAL_TEMP_RAW, 'H', EXTERNAL_TEMP_RAW_DATA_OFFSET, int),
    EncodingParams(OptaaAcMmpCdsParserDataParticleKey.INTERNAL_TEMP_RAW, 'H', INTERNAL_TEMP_RAW_DATA_OFFSET, int),
    EncodingParams(OptaaAcMmpCdsParserDataParticleKey.C_REFERENCE_DARK_COUNTS, 'H',
                   C_REFERENCE_DARK_COUNTS_DATA_OFFSET, int),
    EncodingParams(OptaaAcMmpCdsParserDataParticleKey.C_SIGNAL_DARK_COUNTS, 'H',
                   C_SIGNAL_DARK_COUNTS_DATA_OFFSET, int),
    EncodingParams(OptaaAcMmpCdsParserDataParticleKey.ELAPSED_RUN_TIME, 'I', ELAPSED_RUN_TIME_DATA_OFFSET, int),
    EncodingParams(OptaaAcMmpCdsParserDataParticleKey.NUM_WAVELENGTHS, 'B', NUM_WAVELENGTHS_DATA_OFFSET, int)]


class OptaaAcMmpCdsParserDataParticle(MmpCdsParserDataParticle):
    """
    Class for parsing data from the optaa_ac_mmp_cds data set
    """

    _data_particle_type = DataParticleType.INSTRUMENT
    
    def _get_mmp_cds_subclass_particle_params(self, subclass_specific_msgpack_unpacked_data):
        """
        This method is required to be implemented by classes that extend the MmpCdsParserDataParticle class.
        This implementation returns the particle parameters specific for OptaaAcMmpCds.  As noted in the
        base, it is okay to allow the following exceptions to propagate: ValueError, TypeError, IndexError, KeyError.
        @returns a list of particle params specific to OptaaAcMmpCds
        """

        # Default the subclass particle params to an empty list
        subclass_particle_params = []

        # Init the number of wavelengths to 0
        num_wavelengths = 0

        # Let's iterate through the list of ENCODING_PARAMS to obtain encoding data to use to extract
        # specific particle data
        for encodingParam in ENCODING_PARAMS:
            # Use the encoding param unpack code and unpack offset to unpack a parameter
            param_value = struct.unpack_from(encodingParam.unpack_code,
                                             subclass_specific_msgpack_unpacked_data,
                                             encodingParam.unpack_from_offset)[0]
            # Encode the extracted parameter value using the applicable encoding type
            encoded_param_value = self._encode_value(encodingParam.key,
                                                     param_value,
                                                     encodingParam.encode_type)

            # If the encoding parameter ket is NUM_WAVELENGTHS, let's save the parameter value off, as
            # we will need it for the reference and signal counts later
            if encodingParam.key == OptaaAcMmpCdsParserDataParticleKey.NUM_WAVELENGTHS:
                num_wavelengths = param_value

            # Append each encoded parameter value to the list we will return
            subclass_particle_params.append(encoded_param_value)

        # For the serial number parameter, we need to do a bit more.  Let's first unpack the serial number parts
        serial_number_array = struct.unpack_from('BBB', subclass_specific_msgpack_unpacked_data,
                                                 SERIAL_NUMBER_DATA_OFFSET)

        # Now let's compute the serial number given the parts, using bit shifts
        serial_number_int = (serial_number_array[0] << 16) + (serial_number_array[1] << 8) + (serial_number_array[2])
        # Now let's encode the serial number as an int, and add it to the list we will return
        subclass_particle_params.append(self._encode_value(OptaaAcMmpCdsParserDataParticleKey.SERIAL_NUMBER,
                                                           serial_number_int,
                                                           int))

        # Set the offset to the location of the reference and signal counts
        offset = RAW_REF_AND_SIGNAL_COUNTS_BASE_OFFSET
        raw_c_ref_counts = []
        raw_a_ref_counts = []
        raw_c_sig_counts = []
        raw_a_sig_counts = []

        # Time to deal with the wavelengths
        for i in range(1, num_wavelengths+1):
            # The first param is a "c reference count"
            raw_c_ref_counts.append(struct.unpack_from('H', subclass_specific_msgpack_unpacked_data, offset)[0])
            offset += 2
            # Next is the an "a reference count"
            raw_a_ref_counts.append(struct.unpack_from('H', subclass_specific_msgpack_unpacked_data, offset)[0])
            offset += 2
            # Following that is a "c signal count"
            raw_c_sig_counts.append(struct.unpack_from('H', subclass_specific_msgpack_unpacked_data, offset)[0])
            offset += 2
            # Lastly, an "a signal count"
            raw_a_sig_counts.append(struct.unpack_from('H', subclass_specific_msgpack_unpacked_data, offset)[0])
            offset += 2

        # Encode each of the count lists and append the encoded param to the list to return
        subclass_particle_params.append(self._encode_value(OptaaAcMmpCdsParserDataParticleKey.C_REFERENCE_COUNTS,
                                                           raw_c_ref_counts,
                                                           list))
        subclass_particle_params.append(self._encode_value(OptaaAcMmpCdsParserDataParticleKey.A_REFERENCE_COUNTS,
                                                           raw_a_ref_counts,
                                                           list))
        subclass_particle_params.append(self._encode_value(OptaaAcMmpCdsParserDataParticleKey.C_SIGNAL_COUNTS,
                                                           raw_c_sig_counts,
                                                           list))
        subclass_particle_params.append(self._encode_value(OptaaAcMmpCdsParserDataParticleKey.A_SIGNAL_COUNTS,
                                                           raw_a_sig_counts,
                                                           list))

        # We have all we need, let's return the list
        return subclass_particle_params


class OptaaAcMmpCdsParser(MmpCdsParser):

    """
    Class for parsing data obtain from a OPTAA sensor, series A and C, as received from McLane Moored
    Profiler connected to the cabled docking station.
    """

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate a OptaaAcMmpCdsParser object.
        @param config The configuration for this MmpCdsParser parser
        @param state The state the OptaaAcMmpCdsParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the MmpCds data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        """

        # Call the superclass constructor
        super(OptaaAcMmpCdsParser, self).__init__(config,
                                                  state,
                                                  stream_handle,
                                                  state_callback,
                                                  publish_callback,
                                                  *args, **kwargs)
