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

from math import copysign
from functools import partial

from mi.core.log import get_logger
from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, DatasetParserException
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.dataset.dataset_parser import BufferLoadingParser

# start the logger
log = get_logger()

# regex
ROW_REGEX = r'^(.*)$'  # just give me the whole effing row and get out of my way.
ROW_MATCHER = re.compile(ROW_REGEX)


# statekey
class StateKey(BaseEnum):
    POSITION = 'position'
    TIMESTAMP = 'timestamp'


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
    GGLDR_GLDR_ENG_DELAYED = 'ggldr_eng_delayed'
    GGLDR_GLDR_ENG_RECOVERED = 'ggldr_eng_recovered'
    ### Coastal Gliders (CGLDR).
    CGLDR_CTDGV_DELAYED = 'cgldr_ctdgv_delayed'
    CGLDR_CTDGV_RECOVERED = 'cgldr_ctdgv_recovered'
    CGLDR_FLORT_DELAYED = 'cgldr_flort_delayed'
    CGLDR_FLORT_RECOVERED = 'cgldr_flort_recovered'
    CGLDR_DOSTA_DELAYED = 'cgldr_dosta_delayed'
    CGLDR_DOSTA_RECOVERED = 'cgldr_dosta_recovered'
    CGLDR_PARAD_DELAYED = 'cgldr_parad_delayed'
    CGLDR_PARAD_RECOVERED = 'cgldr_parad_recovered'
    CGLDR_GLDR_ENG_DELAYED = 'cgldr_eng_delayed'
    CGLDR_GLDR_ENG_RECOVERED = 'cgldr_eng_recovered'
    # ADCPA data will parsed by a different parser (adcpa.py)


class GgldrCtdgvDelayedParticleKey(DataParticleKey):
    KEY_LIST = [
        'm_present_time',
        'm_present_secs_into_mission',
        'sci_m_present_time',
        'sci_m_present_secs_into_mission',
        'm_gps_lat',
        'm_gps_lon',
        'm_lat',
        'm_lon',
        'sci_water_cond',
        'sci_water_pressure',
        'sci_water_temp'
    ]


class GgldrCtdgvDelayedDataParticle(DataParticle):
    _data_particle_type = DataParticleType.GGLDR_CTDGV_DELAYED

    def build_parsed_values(self, gpd):
        """
        Takes a GliderParser object and extracts CTDGV data from the
        data dictionary and puts the data into a CTDGV Data Particle.

        @param gpd A GliderParser class instance.
        @param result A returned list with sub dictionaries of the data
        """
        if not isinstance(gpd, GliderParser):
            raise SampleException("GGLDR_CTDGV_DELAYED: Object Instance is not \
                                  a Glider Parsed Data object")

        result = []
        for iRecord in range(0, gpd.num_records):
            record = []
            for key in GgldrCtdgvDelayedParticleKey.KEY_LIST:
                if key in gpd.data_keys:
                    # read the value from the gpd dictionary
                    value = gpd.data_dict[key]['Data'][iRecord]

                    # check to see that the value is not a 'NaN'
                    if value == 'NaN':
                        continue

                    # check to see if this is the time stamp
                    if key == 'm_present_time':
                        self.set_internal_timestamp(float(value))

                    # check to see if this is a lat/longitude string
                    if '_lat' in key or '_lon' in key:
                        # convert latitiude/longitude strings to decimal degrees
                        value = GliderParser._string_to_ddegrees(value)
                    else:
                        # otherwise store the values as floats
                        value = float(value)

                    # add the value to the record
                    record.append({DataParticleKey.VALUE_ID: key,
                                   DataParticleKey.VALUE: value})

                else:
                    log.warn("GGLDR_CTDGV_DELAYED: The particle defined in the \
                             ParticleKey, %s, is not present in the current \
                             data set", key)

            # add the record to total results
            result.append(record)

        return result


class GgldrDostaDelayedParticleKey(DataParticleKey):
    KEY_LIST = [
        'm_present_time',
        'm_present_secs_into_mission',
        'sci_m_present_time',
        'sci_m_present_secs_into_mission',
        'm_gps_lat',
        'm_gps_lon',
        'm_lat',
        'm_lon',
        'sci_oxy4_oxygen',
        'sci_oxy4_saturation',
        ]


class GgldrDostaDelayedDataParticle(DataParticle):
    _data_particle_type = DataParticleType.GGLDR_DOSTA_DELAYED

    def build_parsed_values(self, gpd):
        """
        Takes a GliderParser object and extracts DOSTA data from the
        data dictionary and puts the data into a DOSTA Data Particle.

        @param gpd A GliderParser class instance.
        @param result A returned list with sub dictionaries of the data
        """
        if not isinstance(gpd, GliderParser):
            raise SampleException("GGLDR_DOSTA_DELAYED: Object Instance is not \
                                  a GliderParser object")

        result = []
        for iRecord in range(0, gpd.num_records):
            record = []
            for key in GgldrDostaDelayedParticleKey.KEY_LIST:
                if key in gpd.data_keys:
                    # read the value from the gpd dictionary
                    value = gpd.data_dict[key]['Data'][iRecord]

                    # check to see that the value is not a 'NaN'
                    if value == 'NaN':
                        continue

                    # check to see if this is the time stamp
                    if key == 'm_present_time':
                        self.set_internal_timestamp(float(value))

                    # check to see if this is a lat/longitude string
                    if '_lat' in key or '_lon' in key:
                        # convert latitiude/longitude strings to decimal degrees
                        value = GliderParser._string_to_ddegrees(value)
                    else:
                        # otherwise store the values as floats
                        value = float(value)

                    # add the value to the record
                    record.append({DataParticleKey.VALUE_ID: key,
                                   DataParticleKey.VALUE: value})

                else:
                    log.warn("GGLDR_DOSTA_DELAYED: The particle defined in the \
                             ParticleKey, %s, is not present in the current \
                             data set", key)

            # add the record to total results
            result.append(record)

        return result


class GgldrFlordDelayedParticleKey(DataParticleKey):
    KEY_LIST = [
        'm_present_time',
        'm_present_secs_into_mission',
        'sci_m_present_time',
        'sci_m_present_secs_into_mission',
        'm_gps_lat',
        'm_gps_lon',
        'm_lat',
        'm_lon',
        'sci_flbb_bb_units',
        'sci_flbb_chlor_units',
    ]


class GgldrFlordDelayedDataParticle(DataParticle):
    _data_particle_type = DataParticleType.GGLDR_FLORD_DELAYED

    def build_parsed_values(self, gpd):
        """
        Takes a GliderParser object and extracts FLORD data from the
        data dictionary and puts the data into a FLORD Data Particle.

        @param gpd A GliderParser class instance.
        @param result A returned list with sub dictionaries of the data
        """
        if not isinstance(gpd, GliderParser):
            raise SampleException("GGLDR_FLORD_DELAYED: Object Instance is not \
                                  a GliderParser object")

        result = []
        for iRecord in range(0, gpd.num_records):
            record = []
            for key in GgldrFlordDelayedParticleKey.KEY_LIST:
                if key in gpd.data_keys:
                    # read the value from the gpd dictionary
                    value = gpd.data_dict[key]['Data'][iRecord]

                    # check to see that the value is not a 'NaN'
                    if value == 'NaN':
                        continue

                    # check to see if this is the time stamp
                    if key == 'm_present_time':
                        self.set_internal_timestamp(float(value))

                    # check to see if this is a lat/longitude string
                    if '_lat' in key or '_lon' in key:
                        # convert latitiude/longitude strings to decimal degrees
                        value = GliderParser._string_to_ddegrees(value)
                    else:
                        # otherwise store the values as floats
                        value = float(value)

                    # add the value to the record
                    record.append({DataParticleKey.VALUE_ID: key,
                                   DataParticleKey.VALUE: value})

                else:
                    log.warn("GGLDR_FLORD_DELAYED: The particle defined in the \
                             ParticleKey, %s, is not present in the current \
                             data set", key)

            # add the record to total results
            result.append(record)

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
        'sci_m_present_time',
        'sci_m_present_secs_into_mission',
        'x_low_power_status',
    ]


class GgldrEngDelayedDataParticle(DataParticle):
    _data_particle_type = DataParticleType.GGLDR_ENG_DELAYED

    def build_parsed_values(self, gpd):
        """
        Takes a GliderParser object and extracts engineering data from the
        data dictionary and puts the data into a engineering Data Particle.

        @param gpd A GliderParser class instance.
        @param result A returned list with sub dictionaries of the data
        """
        if not isinstance(gpd, GliderParser):
            raise SampleException("GGLDR_ENG_DELAYED: Object Instance is not \
                                  a GliderParser object")

        result = []
        for iRecord in range(0, gpd.num_records):
            record = []
            for key in GgldrEngDelayedParticleKey.KEY_LIST:
                if key in gpd.data_keys:
                    # read the value from the gpd dictionary
                    value = gpd.data_dict[key]['Data'][iRecord]

                    # check to see that the value is not a 'NaN'
                    if value == 'NaN':
                        continue

                    # check to see if this is the time stamp
                    if key == 'm_present_time':
                        self.set_internal_timestamp(float(value))

                    # check to see if this is a latitude/longitude string
                    if '_lat' in key or '_lon' in key:
                        # convert latitiude/longitude strings to decimal degrees
                        value = GliderParser._string_to_ddegrees(value)
                    else:
                        # otherwise store the values as floats
                        value = float(value)

                    # add the value to the record
                    record.append({DataParticleKey.VALUE_ID: key,
                                   DataParticleKey.VALUE: value})

                else:
                    log.warn("GGLDR_ENG_DELAYED: The particle defined in the \
                             ParticleKey, %s, is not present in the current \
                             data set", key)

            # add the record to total results
            result.append(record)

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
        self._read_state = {StateKey.POSITION: 0, StateKey.TIMESTAMP: 0.0}

        if state:
            self.set_state(self._state)

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. Should be a list with
        a StateKey.POSITION value and StateKey.TIMESTAMP value. The position is
        number of bytes into the file, the timestamp is an NTP4 format timestamp.
        @throws DatasetParserException if there is a bad state structure
        """
        log.trace("Attempting to set state to: %s", state_obj)
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not ((StateKey.POSITION in state_obj) and (StateKey.TIMESTAMP in state_obj)):
            raise DatasetParserException("Invalid state keys")

        self._timestamp = state_obj[StateKey.TIMESTAMP]
        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        # seek to it
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, increment, timestamp):
        """
        Increment the parser position by a certain amount in bytes. This
        indicates what has been READ from the file, not what has been published.
        The increment takes into account a timestamp of WHEN in the data the
        position corresponds to. This allows a reload of both timestamp and the
        position.

        This is a base implementation, override as needed.

        @param increment Number of bytes to increment the parser position.
        @param timestamp The timestamp completed up to that position
        """
        log.trace("Incrementing current state: %s with inc: %s, timestamp: %s",
                  self._read_state, increment, timestamp)

        self._read_state[StateKey.POSITION] += increment
        self._read_state[StateKey.TIMESTAMP] = timestamp
        # Thomas, my monkey of a son, wanted this inserted in the code.

    def _read_data(data):
        """
        Read in the column labels, data type, number of bytes of each
        data type, and the data from an ASCII glider data file.
        """
        # read the column labels, data types and number of bytes of each data
        # type from the first three data rows.
        column_labels = data[0].split()
        column_type = data[1].split()
        column_num_bytes = data[2].split()

        # use np.array's ability to grab the columns of an array
        data_array = np.array(data[3:])  # NOTE: this is an array of strings

        # warn if # of described data rows != to amount read in.
        num_columns = int(self.hdr_dict['sensors_per_cycle'])
        if num_columns != data_array.shape[1]:
            raise DatasetParserException('Glider data file does not have the ' +
                                         'same number of columns as described ' +
                                         'in the header.\n' +
                                         'Described: %d, Actual: %d' %
                                         (num_columns, data_array.shape[1]))

        # extract data to dictionary
        for ii in range(num_columns):
            self.data_dict[column_labels[ii]] = {
                'Name': column_labels[ii],
                'Units': column_type[ii],
                'Number_of_Bytes': int(column_num_bytes[ii]),
                'Data': data_array[:, ii]
            }

        # set additional output values
        self.data_keys = column_labels
        self.num_records = data_array.shape[0]
        
        return 

    def parse_chunks(self):
        """
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list is returned if nothing was
            parsed.
        """
        # set defaults
        result_particles = []
        data = []
        num_hdr_lines = 14
        row_count = 0

        # collect the data from the file
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
        while chunk is not None:
            position = end
            row_match = ROW_MATCHER.match(chunk)
            if row_match:
                # process the header and data rows
                row_count += 1
                if row_count <= num_hdr_lines:
                    # Read in the self describing header lines of an ASCII
                    # glider data file.
                    split_line = chunk.split()
                    if 'num_ascii_tags' in split_line:
                        num_hdr_lines = int(split_line[1])
                    self.hdr_dict[split_line[0][:-1]] = split_line[1]
                else:  # otherwise its data
                    data.append(chunk.split())
            # process the next chunk, all the way through the file.
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

        if row_count > num_hdr_lines + 3:
            # create the data dictionaries
            gpd = self._read_data(data)

            # [TODO: How do we get gpd from _read_data and how to we pass it to _extract_sample below]

            # particlize the dictionaries
            self._timestamp = self._string_to_timestamp(hdr_dict['fileopen_time'])
            self._increment_state(position, self._timestamp)
            result_particles = self._extract_sample(self._particle_class, ROW_MATCHER,
                                                    gpd, self._timestamp)
        else:
            log.warn("This file is empty")

        # publish the results
        return result_particles

    @staticmethod
    def _string_to_ddegrees(pos_str):
        """
        Converts the given string from this data stream into a more
        standard latitude/longitude value in decimal degrees.
        @param pos_str The position (latitude or longitude) string in the
            format "DDMM.MMMM" for latitude and "DDDMM.MMMM" for longitude. A
            positive or negative sign to the string indicates north/south or
            east/west, respectively.
        @retval The position in decimal degrees
        """
        minutes = float(pos_str[-7:])
        degrees = float(pos_str[0:-7])
        ddegrees = copysign((abs(degrees) + minutes / 60), degrees)
        return ddegrees

    @staticmethod
    def _string_to_timestamp(ts_str):
        """
        Converts the given string from this data stream's format into an NTP
        timestamp. This is very likely instrument specific.
        @param ts_str The timestamp string in the format "mm/dd/yyyy hh:mm:ss"
        @retval The NTP4 timestamp
        """
        tstr = re.sub(r"__", "_0", ts_str)
        systime = time.strptime(tstr, "%a_%b_%d_%H:%M:%S_%Y")
        ntptime = ntplib.system_to_ntp_time(time.mktime(systime))
        log.trace("Converted time \"%s\" into %s", ts_str, ntptime)
        return ntptime

