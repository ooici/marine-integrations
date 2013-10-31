#!/usr/bin/env python
"""
@package glider.py
@file glider.py
@author Stuart Pearce & Chris Wingard
@brief Module containing parser scripts for glider data set agents
"""
__author__ = 'Stuart Pearce & Chris Wingard'
__license__ = 'Apache 2.0'

import re
import numpy as np
import ntplib
import time
import copy
import pdb

from math import copysign
from functools import partial

from mi.core.log import get_logger
from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, DatasetParserException
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.instrument.data_particle import DataParticleValue
from mi.dataset.dataset_parser import BufferLoadingParser

# start the logger
log = get_logger()

###############################################################################
# Define the Particle Classes for Global and Coastal Gliders, both the delayed
# (delivered over Iridium network) and the recovered (downloaded from a glider
# upon recovery) data sets.
#
# [TODO: Confirm parameter lists with Project Scientist and System Engineers]
#
# [TODO: Build Particle classes for recovered datasets]
#
# [TODO: Determine method for adding a different suite of O2 values for Glider
# ooi_247. This glider uses a different O2 sensor that has a different set of
# parameters than all other OOI gliders]
#
###############################################################################
class StateKey(BaseEnum):
    POSITION = 'position'


class DataParticleType(BaseEnum):
    # Data particle types for the Open Ocean (aka Global) and Coastal gliders.
    # ADCPA data will parsed by a different parser (adcpa.py)
    ### Global Gliders (GGLDR).
    GGLDR_CTDGV_DELAYED = 'ggldr_ctdgv_delayed'
    GGLDR_CTDGV_RECOVERED = 'ggldr_ctdgv_recovered'
    GGLDR_FLORD_DELAYED = 'ggldr_flord_delayed'
    GGLDR_FLORD_RECOVERED = 'ggldr_flord_recovered'
    GGLDR_DOSTA_DELAYED = 'ggldr_dosta_delayed'
    GGLDR_DOSTA_RECOVERED = 'ggldr_dosta_recovered'
    GGLDR_ENG_DELAYED = 'ggldr_eng_delayed'
    GGLDR_ENG_RECOVERED = 'ggldr_eng_recovered'
    ### Coastal Gliders (CGLDR).
    CGLDR_CTDGV_DELAYED = 'cgldr_ctdgv_delayed'
    CGLDR_CTDGV_RECOVERED = 'cgldr_ctdgv_recovered'
    CGLDR_FLORT_DELAYED = 'cgldr_flort_delayed'
    CGLDR_FLORT_RECOVERED = 'cgldr_flort_recovered'
    CGLDR_DOSTA_DELAYED = 'cgldr_dosta_delayed'
    CGLDR_DOSTA_RECOVERED = 'cgldr_dosta_recovered'
    CGLDR_PARAD_DELAYED = 'cgldr_parad_delayed'
    CGLDR_PARAD_RECOVERED = 'cgldr_parad_recovered'
    CGLDR_ENG_DELAYED = 'cgldr_eng_delayed'
    CGLDR_ENG_RECOVERED = 'cgldr_eng_recovered'

class GliderParticleKey(BaseEnum):
    """
    Common glider particle parameters
    """
    M_PRESENT_SECS_INTO_MISSION = 'm_present_secs_into_mission'
    M_PRESENT_TIME = 'm_present_time'  # you need the m_ timestamps for lats & lons
    SCI_M_PRESENT_TIME = 'sci_m_present_time'
    SCI_M_PRESENT_SECS_INTO_MISSION = 'sci_m_present_secs_into_mission'

    @classmethod
    def science_parameter_list(cls):
        """
        Get a list of all science parameters
        """
        result = []
        for key in cls.list():
            if key not in GliderParticleKey.list():
                result.append(key)

        return result

class GliderParticle(DataParticle):
    """
    Base particle for glider data.  Glider files are
    publishing as a particle rather than a raw data string.  This is in
    part to solve the dynamic nature of a glider file and not having to
    hard code >2000 variables in a regex.

    This class should be a parent class to all the data particle classes
    associated with the glider.
    """

    # It is possible that record could be parsed, but they don't
    # contain actual science data for this instrument.  This flag
    # will be set to true if we have found data when parsed.
    common_parameters = GliderParticleKey.list()

    def _parsed_values(self, key_list):
        log.debug("Build a particle with keys: %s", key_list)
        if not isinstance(self.raw_data, dict):
            raise SampleException(
                "%s: Object Instance is not a Glider Parsed Data \
                dictionary" % self._data_particle_type)

        result = []

        # find if any of the variables from the particle key list are in
        # the data_dict and keep it
        for key in key_list:
            if key in self.raw_data:
                # read the value from the gpd dictionary
                value = self.raw_data[key]['Data']

                # check to see that the value is not a 'NaN'
                if np.isnan(value):
                    log.trace("NaN Value: %s", key)
                    value = None

                # add the value to the record
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: value})
                log.trace("Key: %s, value: %s", key, value)

            else:
                #log.warn("The particle defined in the" +
                #         "ParticleKey, %s, is not present in the current" % key +
                #         "data set. Confirm by checking the m, s, or tbdlist of " +
                #         "the glider to insure this is expected, or check the " +
                #         "standard lists and/or Particle Keys")
                SampleException("%s column missing from datafile, row ignored", key)

        return result

class CtdgvParticleKey(GliderParticleKey):
    SCI_WATER_COND = 'sci_water_cond'
    SCI_WATER_PRESSURE = 'sci_water_pressure'
    SCI_WATER_TEMP = 'sci_water_temp'


class GgldrCtdgvDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.GGLDR_CTDGV_DELAYED
    science_parameters = CtdgvParticleKey.science_parameter_list()

    def _build_parsed_values(self):
        """
        Extracts CTDGV data from the glider data dictionary intiallized with
        the particle class and puts the data into a CTDGV Data Particle.

        @param result A returned list with sub dictionaries of the data
        """
        return self._parsed_values(CtdgvParticleKey.list())


class CgldrCtdgvDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.CGLDR_CTDGV_DELAYED

    def _build_parsed_values(self):
        """
        Extracts CTDGV data from the glider data dictionary intiallized with
        the particle class and puts the data into a CTDGV Data Particle.

        @param result A returned list with sub dictionaries of the data
        """
        return self._parsed_values(CtdgvParticleKey.KEY_LIST)


class DostaParticleKey(GliderParticleKey):
    SCI_OXY4_OXYGEN = 'sci_oxy4_oxygen'
    SCI_OXY4_SATURATION = 'sci_oxy4_saturation'


class GgldrDostaDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.GGLDR_DOSTA_DELAYED
    science_parameters = DostaParticleKey.science_parameter_list()

    def _build_parsed_values(self):
        """
        Takes a GliderParser object and extracts DOSTA data from the
        data dictionary and puts the data into a DOSTA Data Particle.

        @param gpd A GliderParser class instance.
        @param result A returned list with sub dictionaries of the data
        """
        return self._parsed_values(DostaParticleKey.list())


class CgldrDostaDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.CGLDR_DOSTA_DELAYED

    def _build_parsed_values(self):
        """
        Takes a GliderParser object and extracts DOSTA data from the
        data dictionary and puts the data into a DOSTA Data Particle.

        @param gpd A GliderParser class instance.
        @param result A returned list with sub dictionaries of the data
        """
        return self._parsed_values(DostaParticleKey.KEY_LIST)


class FlordParticleKey(GliderParticleKey):
    SCI_FLBB_BB_UNITS = 'sci_flbb_bb_units'
    SCI_FLBB_CHLOR_UNITS = 'sci_flbb_chlor_units'


class GgldrFlordDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.GGLDR_FLORD_DELAYED
    science_parameters = FlordParticleKey.science_parameter_list()

    def _build_parsed_values(self):
        """
        Takes a GliderParser object and extracts FLORD data from the
        data dictionary and puts the data into a FLORD Data Particle.

        @param result A returned list with sub dictionaries of the data
        @throws SampleException if the data is not a glider data dictionary
            produced by GliderParser._read_data
        """
        return self._parsed_values(FlordParticleKey.list())


class FlortParticleKey(DataParticleKey):
    KEY_LIST = [
        'm_gps_lat',
        'm_gps_lon',
        'm_lat',
        'm_lon',
        'sci_flbbcd_bb_units',
        'sci_flbbcd_cdom_units'
        'sci_flbbcd_chlor_units',
        'm_present_time',  # need m_ timestamps for lats & lons
        'm_present_secs_into_mission',
        'sci_m_present_time',
        'sci_m_present_secs_into_mission'
    ]


class CgldrFlortDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.CGLDR_FLORT_DELAYED

    def _build_parsed_values(self):
        """
        Takes a GliderParser object and extracts FLORD data from the
        data dictionary and puts the data into a FLORD Data Particle.

        @param result A returned list with sub dictionaries of the data
        @throws SampleException if the data is not a glider data dictionary
            produced by GliderParser._read_data
        """
        return self._parsed_values(FlordParticleKey.KEY_LIST)


class EngineeringParticleKey(GliderParticleKey):
    # [TODO: This key list will need to be adjusted once confirmation is received from PS/SE]
    BATT_POS = 'c_battpos'
    WPT_LAT = 'c_wpt_lat'
    WPT_LON = 'c_wpt_lon'
    BATT_POS = 'm_battpos'
    COULOMB_AMPHR_TOTAL = 'm_coulomb_amphr_total'
    COULOMB_CURRENT = 'm_coulomb_current'
    DEPTH = 'm_depth'
    DE_OIL_VOL = 'm_de_oil_vol'
    GPS_LAT = 'm_gps_lat'
    GPS_LON = 'm_gps_lon'
    LAT = 'm_lat'
    LON = 'm_lon'
    HEADING = 'm_heading'
    PITCH = 'm_pitch'
    SPEED = 'm_speed'
    WATER_VX = 'm_water_vx'
    WATER_VY = 'm_water_vy'
    LOW_POWER_STATUS = 'x_low_power_status'


class GgldrEngDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.GGLDR_ENG_DELAYED
    science_parameters = EngineeringParticleKey.science_parameter_list()

    def _build_parsed_values(self):
        """
        Takes a GliderParser object and extracts engineering data from the
        data dictionary and puts the data into a engineering Data Particle.

        @param result A returned list with sub dictionaries of the data
        @throws SampleException if the data is not a glider data dictionary
            produced by GliderParser._read_data
        """
        return self._parsed_values(EngineeringParticleKey.list())


class CgldrEngDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.CGLDR_ENG_DELAYED

    def _build_parsed_values(self):
        """
        Takes a GliderParser object and extracts engineering data from the
        data dictionary and puts the data into a engineering Data Particle.

        @param result A returned list with sub dictionaries of the data
        @throws SampleException if the data is not a glider data dictionary
            produced by GliderParser._read_data
        """
        return self._parsed_values(EngineeringParticleKey.KEY_LIST)


class ParadParticleKey(DataParticleKey):
    KEY_LIST = [
        'm_present_time',  # need m_ timestamps for lats & lons
        'm_present_secs_into_mission',
        'sci_m_present_time',
        'sci_m_present_secs_into_mission'
        'm_gps_lat',
        'm_gps_lon',
        'm_lat',
        'm_lon',
        'sci_bsipar_par'
    ]


class CgldrParadDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.CGLDR_PARAD_DELAYED

    def _build_parsed_values(self):
        """
        Takes a GliderParser object and extracts engineering data from the
        data dictionary and puts the data into a engineering Data Particle.

        @param result A returned list with sub dictionaries of the data
        @throws SampleException if the data is not a glider data dictionary
            produced by GliderParser._read_data
        """
        return self._parsed_values(ParadParticleKey.KEY_LIST)


class GliderParser(BufferLoadingParser):
    """
    GliderParser parses a Slocum Electric Glider data file that has been
    converted to ASCII from binary and merged with it's corresponding flight or
    science data file, and holds the self describing header data in a header
    dictionary and the data in a data dictionary using the column labels as the
    dictionary keys. These dictionaries are used to build the particles.
    """
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):

        self._stream_handle = stream_handle
        self._timestamp = 0.0
        self._record_buffer = []  # holds tuples of (record, state)
        self._read_state = {StateKey.POSITION: 0}
        self._read_header()

        record_regex = re.compile(r'.*\n')
        self._sample_regex = self._get_sample_pattern()
        self._whitespace_regex = re.compile(r'\s*$')

        super(GliderParser, self).__init__(config,
                                           self._stream_handle,
                                           state,
                                           partial(StringChunker.regex_sieve_function,
                                                   regex_list=[record_regex]),
                                           state_callback,
                                           publish_callback,
                                           *args,
                                           **kwargs)
        if state:
            self.set_state(self._state)

    def _read_header(self):
        """
        Read the header for a glider file.
        @raise SampleException if we fail to parse the header.
        """
        self._header_dict = {}

        if self._stream_handle.tell() != 0:
            log.error("Attempting to call _read_header after file parsing has already started")
            raise SampleException("Can not call _read_header now")

        # Read and store the configuration found in the 14 line header
        self._read_file_definition()
        self._read_column_labels()

        # What file position are we now?
        file_position = self._stream_handle.tell()
        self._read_state[StateKey.POSITION] = file_position

    def _get_sample_pattern(self):
        """
        Generate a sample regex based on the column header.
        @return compiled regex matching data records.
        """
        column_count = self._header_dict.get('sensors_per_cycle')
        if column_count is None:
            raise SampleException("sensors_per_cycle not defined")

        if column_count == 0:
            raise SampleException("sensors_per_cycle is 0")

        regex = r''
        for i in range(0, column_count-1):
            regex += r'([-\d\.e]+|NaN)\s'

        regex += r'([-\d\.e]+|NaN)\s*$'

        log.debug("Sample Pattern: %s", regex)
        return re.compile(regex, re.MULTILINE)

    def _read_file_definition(self):
        """
        Read the first 14 lines of the data file for the file definitions, values
        are colon delimited key value pairs.  The pairs are parsed and stored in
        header_dict member.
        """
        row_count = 0
        num_hdr_lines = 14

        header_pattern = r'(.*): (.*)$'
        header_re = re.compile(header_pattern)

        while row_count < num_hdr_lines:
            line = self._stream_handle.readline()
            log.debug("Parse header position: %s line: %s", self._stream_handle.tell(), line)

            match = header_re.match(line)

            if match:
                key = match.group(1)
                value = match.group(2)
                value = value.strip()
                log.debug("header key: %s, value: %s", key, value)

                # update num_hdr_lines based on the header info.
                if key in ['num_ascii_tags', 'num_label_lines', 'sensors_per_cycle']:
                    value = int(value)

                self._header_dict[key] = value
            else:
                log.warn("Failed to parse header row: %s.", line)

            row_count += 1

    def _read_column_labels(self):
        """
        Read the next three lines to populate column data.

        Row 1 == labels
        Row 2 == units
        Row 3 == column byte size

        Currently we are only able to support 3 label line rows.  If num_label_lines !=
        3 then raise an exception.
        """

        if self._header_dict.get('num_label_lines') != 3:
            raise SampleException("Label line count must be 3 for this parser")

        # read the next 3 rows that describe each column of data
        self._header_dict['labels'] = self._stream_handle.readline().strip().split()
        self._header_dict['data_units'] = self._stream_handle.readline().strip().split()
        num_of_bytes = self._stream_handle.readline().strip().split()
        num_of_bytes = map(int, num_of_bytes)
        self._header_dict['num_of_bytes'] = num_of_bytes

        log.debug("Label count: %d", len(self._header_dict['labels']))

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser @param state_obj The
        object to set the state to. Should be a dict with a StateKey.POSITION
        value. The position is number of bytes into the file.
        @throws DatasetParserException if there is a bad state structure
        """
        log.trace("Attempting to set state to: %s", state_obj)
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not (StateKey.POSITION in state_obj):
            raise DatasetParserException("Invalid state keys")

        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        # seek to it
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, increment):
        """
        Increment the parser position by a certain amount in bytes. This
        indicates what has been READ from the file, not what has been published.
        This allows a reload of the file position.

        @param increment Number of bytes to increment the parser position.
        """
        log.trace("Incrementing current state: %s with inc: %s",
                  self._read_state, increment)
        self._read_state[StateKey.POSITION] += increment
        # Thomas, my monkey of a son, wanted this comment inserted in the code. -CW

    def _read_data(self, data_record):
        """
        Read in the column labels, data type, number of bytes of each
        data type, and the data from an ASCII glider data file.
        """
        log.debug("_read_data: Data Record: %s", data_record)

        data_dict = {}
        num_columns = self._header_dict['sensors_per_cycle']
        data_labels = self._header_dict['labels']
        #data_units = self._header_dict['data_units']
        num_bytes = self._header_dict['num_of_bytes']
        data = data_record.strip().split()
        log.trace("Split data: %s", data)
        if num_columns != len(data):
            raise DatasetParserException('Glider data file does not have the ' +
                                         'same number of columns as described ' +
                                         'in the header.\n' +
                                         'Described: %d, Actual: %d' %
                                         (num_columns, len(data)))

        # extract record to dictionary
        for ii in range(num_columns):
            log.trace("_read_data: index: %d label: %s, value: %s", ii, data_labels[ii], data[ii])

            if (num_bytes[ii] == 1) or (num_bytes[ii] == 2):
                    str2data = int
            elif (num_bytes[ii] == 4) or (num_bytes[ii] == 8):
                    str2data = float

            # check to see if this is a latitude/longitude string
            if ('_lat' in data_labels[ii]) or ('_lon' in data_labels[ii]):
                # convert latitiude/longitude strings to decimal degrees

                value = self._string_to_ddegrees(data[ii])
            else:
                value = str2data(data[ii])

            data_dict[data_labels[ii]] = {
                'Name': data_labels[ii],
                #'Units': data_units[ii],
                #'Number_of_Bytes': int(num_bytes[ii]),
                'Data': value
            }

        log.trace("Data dict parsed: %s", data_dict)
        return data_dict

    def get_block(self, size=1024):
        """
        Need to overload the base class behavior so we can get the last
        record if it doesn't end with a newline it would be ignored.
        """
        len = super(GliderParser, self).get_block(size)
        log.debug("Buffer read bytes: %d", len)

        if len != size:
            self._chunker.add_chunk("\n", self._timestamp)

        return len

    def _sload_particle_buffer(self):
        """
        Need to overload the base class behavior so we can get the last
        record if it doesn't end with a newline it would be ignored.
        """
        bytes_read = self.get_block(1024)

        while bytes_read > 0:
            # Add a newline if we have read the last byte of the file
            # This ensures the last record will be \n terminated.
            if bytes_read < 1024:
                self._chunker.add_chunk("\n", self._timestamp)
            result = self.parse_chunks()
            self._record_buffer.extend(result)

    def parse_chunks(self):
        """
        Create particles out of chunks and raise an event
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list is returned if nothing was
            parsed.
        """
        # set defaults
        result_particles = []

        log.debug("BUFFER: %s", self._chunker.buffer)
        # collect the data from the file
        (timestamp, data_record, start, end) = self._chunker.get_next_data_with_index()

        while data_record is not None:
            log.debug("data record: %s", data_record)
            if self._sample_regex.match(data_record):
                # parse the data record into a data dictionary to pass to the
                # particle class
                data_dict = self._read_data(data_record)

                # from the parsed data, m_present_time is the unix timestamp
                try:
                    record_time = data_dict['m_present_time']['Data']
                    timestamp = ntplib.system_to_ntp_time(data_dict['m_present_time']['Data'])
                    log.debug("Converting record timestamp %f to ntp timestamp %f", record_time, timestamp)
                except KeyError:
                    raise SampleException("unable to find timestamp in data")

                if self._has_science_data(data_dict):
                    # create the particle
                    particle = self._extract_sample(self._particle_class, None, data_dict, timestamp)
                    self._increment_state(end)
                    result_particles.append((particle, copy.copy(self._read_state)))
                else:
                    log.debug("No science data found in particle. %s", data_dict)

            elif self._whitespace_regex.match(data_record):
                log.debug("Only whitespace detected in record.  Ignoring.")
            else:
                log.error("Data record did not match data pattern.  Failed parsing: '%s'", data_record)
                raise SampleException("data record does not match sample pattern")

            (timestamp, data_record, start, end) = self._chunker.get_next_data_with_index()

        # publish the results
        return result_particles

    def _has_science_data(self, data_dict):
        """
        Examine the data_dict to see if it contains science data.
        """
        log.debug("Looking for data in science parameters: %s", self._particle_class.science_parameters)
        for key in data_dict.keys():
            if key in self._particle_class.science_parameters:
                value = data_dict[key]['Data']
                if not np.isnan(value):
                    log.debug("Found science value for key: %s, value: %s", key, value)
                    return True
                else:
                    log.debug("Science data value is nan: %s %s", key, value)

        log.debug("No science data found!")
        return False

    def _string_to_ddegrees(self, pos_str):
        """
        Converts the given string from this data stream into a more
        standard latitude/longitude value in decimal degrees.
        @param pos_str The position (latitude or longitude) string in the
            format "DDMM.MMMM" for latitude and "DDDMM.MMMM" for longitude. A
            positive or negative sign to the string indicates northern/southern
            or eastern/western hemispheres, respectively.
        @retval The position in decimal degrees
        """
        log.debug("Convert lat lon to degrees: %s", pos_str)

        # If NaN then return NaN
        if np.isnan(float(pos_str)):
            return float(pos_str)

        # It appears that in some cases lat/lon is "0" not a decimal format as
        # indicated above.  While 0 is a valid lat/lon measurement we think
        # because it is not in decimal form it is an erroneous value.
        if pos_str == "0":
            log.warn("0 value found for lat/lon, not parsing, return NaN")
            return float("NaN")

        # As a stop gap fix add a .0 to integers that don't contain a decimal.  This
        # should only affect the engineering stream as the science data streams shouldn't
        # contain lat lon
        if not "." in pos_str:
            pos_str += ".0"

        regex = r'(-*\d{2,3})(\d{2}.\d+)'
        regex_matcher = re.compile(regex)
        latlon_match = regex_matcher.match(pos_str)

        if latlon_match is None:
            raise SampleException("Failed to parse lat/lon value: '%s'" % pos_str)

        degrees = float(latlon_match.group(1))
        minutes = float(latlon_match.group(2))
        ddegrees = copysign((abs(degrees) + minutes / 60.), degrees)

        return ddegrees

# End of glider.py
