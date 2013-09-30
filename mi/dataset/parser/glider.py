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

# regex
ROW_REGEX = r'^(.+)\n'  # just give me the whole effing row and get out of my way.
ROW_MATCHER = re.compile(ROW_REGEX, re.MULTILINE)


# statekey
class StateKey(BaseEnum):
    POSITION = 'position'


###############################################################################
# Define the Particle Classes for Global and Coastal Gliders, both the delayed
# (delivered over Iridium network) and the recovered (downloaded from a glider
# upon recovery) data sets.
#
# [TODO: Build Particle classes for global recovered datasets and for all
# coastal glider data (delayed and recoverd)]
#
# [TODO: Do we need to add a particle for the file header information?]
#
###############################################################################
class DataParticleType(BaseEnum):
    # Data particle types for the Open Ocean (aka Global) and Coastal gliders
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
    # ADCPA data will parsed by a different parser (adcpa.py)


class GliderParticle(DataParticle):
    """Child class to Data Particle to overwrite the __init__ method so
    that it will accept a data dictionary that holds a data record for
    publishing as a particle rather than a raw data string.  This is in
    part to solve the dynamic nature of a glider file and not having to
    hard code >2000 variables in a regex.

    This class should be a parent class to all the data particle classes
    associated with the glider.

    Admittedly the original __init__ in the DataParticle class could
    have still been used only using the self.raw_data attribute to hold
    the dictionary as it is only used in the child particles (so long as
    the child particles use it as a dictionary). However, this was still
    overwritten for the sake of style and unambiguity.
    """
    def __init__(self, data_dict,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.INTERNAL_TIMESTAMP,
                 quality_flag=DataParticleValue.OK):
        """ Build a particle seeded with appropriate information

        @param raw_data The raw data used in the particle
        @throws SampleException if data_dict is not a glider data dictionary
        """
        self.contents = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.INTERNAL_TIMESTAMP: internal_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: ntplib.system_to_ntp_time(time.time()),
            DataParticleKey.PREFERRED_TIMESTAMP: preferred_timestamp,
            DataParticleKey.QUALITY_FLAG: quality_flag
        }
        if not isinstance(data_dict, dict):
            raise SampleException(
                "%s: Object Instance is not a Glider Parsed Data \
                dictionary" % self._data_particle_type)
        self.data_dict = data_dict


class GldrCtdgvParticleKey(DataParticleKey):
    KEY_LIST = [
        'm_gps_lat',
        'm_gps_lon',
        'm_lat',
        'm_lon',
        'sci_water_cond',
        'sci_water_pressure',
        'sci_water_temp',
        'sci_ctd41cp_timestamp',
        'm_present_time',  # you need the m_ timestamps for lats & lons
        'm_present_secs_into_mission',
        'sci_m_present_time',
        'sci_m_present_secs_into_mission'
    ]


class GgldrCtdgvDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.GGLDR_CTDGV_DELAYED

    def _build_parsed_values(self):
        """
        Extracts CTDGV data from the glider data dictionary intiallized with
        the particle class and puts the data into a CTDGV Data Particle.

        @param result A returned list with sub dictionaries of the data
        """
        result = []

        # find if any of the variables from the particle key list are in
        # the data_dict and keep it
        for key in GldrCtdgvParticleKey.KEY_LIST:
            if key in self.data_dict:
                # read the value from the gpd dictionary
                value = self.data_dict[key]['Data']

                # check to see that the value is not a 'NaN'
                if np.isnan(value):
                    continue

                # add the value to the record
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: value})

            else:
                log.warn("GGLDR_CTDGV_DELAYED: The particle defined in the" +
                         "ParticleKey, %s, is not present in the current" % key +
                         "data set.  Check that the m, s, or tbdlist of " +
                         "the glider are the same as the standard lists, " +
                         "or check the Particle Keys")

        return result


class GldrDostaParticleKey(DataParticleKey):
    KEY_LIST = [
        'm_gps_lat',
        'm_gps_lon',
        'm_lat',
        'm_lon',
        'sci_oxy4_oxygen',
        'sci_oxy4_saturation',
        'm_present_time',  # need the m_ timestamps for lats & lons
        'm_present_secs_into_mission',
        'sci_m_present_time',
        'sci_m_present_secs_into_mission',
        # need the CTD variables too for salinity corrections
        'sci_water_cond',
        'sci_water_temp',
        'sci_water_pressure']


class GgldrDostaDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.GGLDR_DOSTA_DELAYED

    def _build_parsed_values(self):
        """
        Takes a GliderParser object and extracts DOSTA data from the
        data dictionary and puts the data into a DOSTA Data Particle.

        @param gpd A GliderParser class instance.
        @param result A returned list with sub dictionaries of the data
        """

        result = []
        for key in GldrDostaParticleKey.KEY_LIST:
            if key in self.data_dict:
                # read the value from the gpd dictionary
                value = self.data_dict[key]['Data']

                # check to see that the value is not a 'NaN'
                if np.isnan(value):
                    continue

                # add the value to the record
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: value})

            else:
                log.warn("GGLDR_DOSTA_DELAYED: The particle defined in the" +
                         "ParticleKey, %s, is not present in the current" % key +
                         "data set.  Check that the m, s, or tbdlist of " +
                         "the glider are the same as the standard lists, " +
                         "or check the Particle Keys")

        return result


class GldrFlordParticleKey(DataParticleKey):
    KEY_LIST = [
        'm_gps_lat',
        'm_gps_lon',
        'm_lat',
        'm_lon',
        'sci_flbb_bb_units',
        'sci_flbb_chlor_units',
        'm_present_time',  # need m_ timestamps for lats & lons
        'm_present_secs_into_mission',
        'sci_m_present_time',
        'sci_m_present_secs_into_mission'
    ]


class GgldrFlordDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.GGLDR_FLORD_DELAYED

    def _build_parsed_values(self):
        """
        Takes a GliderParser object and extracts FLORD data from the
        data dictionary and puts the data into a FLORD Data Particle.

        @param result A returned list with sub dictionaries of the data
        @throws SampleException if the data is not a glider data dictionary
            produced by GliderParser._read_data
        """

        result = []
        for key in GldrFlordParticleKey.KEY_LIST:
            if key in self.data_dict:
                # read the value from the gpd dictionary
                value = self.data_dict[key]['Data']

                # check to see that the value is not a 'NaN'
                if np.isnan(value):
                    continue

                # add the value to the record
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: value})

            else:
                log.warn("GGLDR_FLORD_DELAYED: The particle defined in the" +
                         "ParticleKey, %s, is not present in the current" % key +
                         "data set.  Check that the m, s, or tbdlist of " +
                         "the glider are the same as the standard lists, " +
                         "or check the Particle Keys")

            # sci_m_present_time is the proper timestamp to use with
            # science variables. However, when no scientific data is published
            # (but glider flight data IS published), sci_m_present_time fills
            # with NaNs. Glider flight data (e.g. lat & lon) is paired with the
            # m_present_time timestamp when published. Unlike
            # sci_m_present_time, m_present_time will always have a value for
            # each record even if no flight data is published.
            # For example:
            # gps_lat       m_present_time      sci_m_present_time     temp
            # 5002.9419     1376510710.50647    NaN                    NaN
            # NaN           1376510712.36099    1376510712.36099       4.01713
            #
            # Unfortunately, m_present_time and sci_m_present_time may not
            # always be equal. So if we were to set the internal_timestamp to
            # the type associated with the relevant data for each record (both
            # types are needed in the science particles), it could cause the
            # internal_timestamp to be non-linear, non-monotonic, or corrupt.
            # To avoid this we will always set the internal_timestamp to the
            # m_present_time timestamp (which is usually close enough for
            # plotting since the timestamps are adjusted during GPS fixes) and
            # users should be aware if downloading data, that
            # sci_m_present_timestamp is the proper timestamp to use with any
            # science variables (i.e. any data handled by the onboard science
            # computer)

            ## Set internal timestamp with sci_m_present_time if available
            #if key is 'sci_m_present_time':
            #    timestamp = ntplib.system_to_ntp_time(self.data_dict[key]['Data'])
            #    self.set_internal_timestamp(timestamp=timestamp)

        return result


class GgldrEngDelayedParticleKey(DataParticleKey):
    KEY_LIST = [
        'c_battpos',
        'c_wpt_lat',
        'c_wpt_lon',
        'm_battpos',
        'm_coulomb_amphr_total',
        'm_coulomb_current',
        'm_depth',
        'm_de_oil_vol',
        'm_gps_lat',
        'm_gps_lon',
        'm_lat',
        'm_lon',
        'm_heading',
        'm_pitch',
        'm_present_time',
        'm_present_secs_into_mission',
        'm_speed',
        'm_water_vx',
        'm_water_vy',
        'x_low_power_status',
    ]


class GgldrEngDelayedDataParticle(GliderParticle):
    _data_particle_type = DataParticleType.GGLDR_ENG_DELAYED

    def _build_parsed_values(self):
        """
        Takes a GliderParser object and extracts engineering data from the
        data dictionary and puts the data into a engineering Data Particle.

        @param result A returned list with sub dictionaries of the data
        @throws SampleException if the data is not a glider data dictionary
            produced by GliderParser._read_data
        """

        result = []
        for key in GgldrEngDelayedParticleKey.KEY_LIST:
            if key in self.data_dict:
                # read the value from the gpd dictionary
                value = self.data_dict[key]['Data']

                # check to see that the value is not a 'NaN'
                if np.isnan(value):
                    continue

                # add the value to the record
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: value})

            else:
                log.warn("GGLDR_ENG_DELAYED: The particle defined in the" +
                         "ParticleKey, %s, is not present in the current" % key +
                         "data set.  Check that the m, s, or tbdlist of " +
                         "the glider are the same as the standard lists, " +
                         "or check the Particle Keys")

        return result


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
        super(GliderParser, self).__init__(config,
                                           stream_handle,
                                           state,
                                           partial(StringChunker.regex_sieve_function,
                                                   regex_list=[ROW_MATCHER]),
                                           state_callback,
                                           publish_callback,
                                           *args,
                                           **kwargs)
        self._timestamp = 0.0
        self._record_buffer = []  # holds tuples of (record, state)
        self._read_state = {StateKey.POSITION: 0}
        self._read_header()
        if state and not(state[StateKey.POSITION] == 0):
        #if state:
            self.set_state(self._state)

    def _read_header(self):
        """
        """
        self._header_dict = {}
        # should be 14 header lines, will double check in self
        # describing header info.
        num_hdr_lines = 14
        row_count = 1
        while row_count <= num_hdr_lines:
            line = self._stream_handle.readline()
            split_line = line.split()
            # update num_hdr_lines based on the header info.
            if 'num_ascii_tags' in split_line:
                num_hdr_lines = int(split_line[1])
            # remove a ':' from the key string below using :-1
            self._header_dict[split_line[0][:-1]] = split_line[1]
            row_count += 1

        # read the next 3 rows that describe each column of data
        self._header_dict['labels'] = self._stream_handle.readline().split()
        self._header_dict['data_units'] = self._stream_handle.readline().split()
        num_of_bytes = self._stream_handle.readline().split()
        num_of_bytes = map(int, num_of_bytes)
        self._header_dict['num_of_bytes'] = num_of_bytes

        # unlikely to ever happen, but if 'num_label_lines' is greater than the
        # 3 read lines just above, then read the extras into the dictionary

        num_label_lines = int(self._header_dict['num_label_lines'])
        if num_label_lines > 3:
            for ii in range(num_label_lines-3):
                key_str = 'unknown_label%d' % ii+1
                self._header_dict[key_str] = self._stream_handle.readline().split()

        # What file position are we now?
        file_position = self._stream_handle.tell()
        # set that to state
        self._read_state[StateKey.POSITION] = file_position

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
        # Thomas, my monkey of a son, wanted this inserted in the code. -CW

    def _read_data(self, data_record):
        """
        Read in the column labels, data type, number of bytes of each
        data type, and the data from an ASCII glider data file.
        """
        data_dict = {}
        num_columns = int(self._header_dict['sensors_per_cycle'])
        data_labels = self._header_dict['labels']
        #data_units = self._header_dict['data_units']
        num_bytes = self._header_dict['num_of_bytes']
        data = data_record.split()
        if num_columns != len(data):
            raise DatasetParserException('Glider data file does not have the ' +
                                         'same number of columns as described ' +
                                         'in the header.\n' +
                                         'Described: %d, Actual: %d' %
                                         (num_columns, len(data)))

        # extract record to dictionary
        for ii in range(num_columns):

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

        return data_dict

    def parse_chunks(self):
        """
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list is returned if nothing was
            parsed.
        """
        # set defaults
        result_particles = []

        # collect the data from the file
        (timestamp, data_record, start, end) = self._chunker.get_next_data_with_index()

        while data_record is not None:
            row_match = ROW_MATCHER.match(data_record)
            if row_match:
                # parse the data record into a data dictionary to pass to the
                # particle class
                data_dict = self._read_data(data_record)

                # from the parsed data, m_present_time is the unix timestamp
                timestamp = ntplib.system_to_ntp_time(data_dict['m_present_time']['Data'])

                # create the particle
                particle = self._particle_class(
                    data_dict, internal_timestamp=timestamp,
                    preferred_timestamp=DataParticleKey.INTERNAL_TIMESTAMP)
                self._increment_state(end)
                result_particles.append((particle, copy.copy(self._read_state)))
                self._timestamp += 1

            # process the next chunk, all the way through the file.
            (timestamp, data_record, start, end) = self._chunker.get_next_data_with_index()

        # TODO: figure out where to log a warning if the file was empty
            #log.warn("This file is empty")

        # publish the results
        return result_particles

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
        if np.isnan(float(pos_str)):
            return float(pos_str)
        regex = r'(-*\d{2,3})(\d{2}.\d+)'
        regex_matcher = re.compile(regex)
        latlon_match = regex_matcher.match(pos_str)
        if latlon_match is None:
            print pos_str, latlon_match
        degrees = float(latlon_match.group(1))
        minutes = float(latlon_match.group(2))
        ddegrees = copysign((abs(degrees) + minutes / 60.), degrees)
        return ddegrees

# End of glider.py
