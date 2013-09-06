#!/usr/bin/env python
"""
@package glider.py
@file glider.py
@author Stuart Pearce & Chris Wingard
@brief Module containing parser scripts for glider data set agents
"""
__author__ = 'Stuart Pearce & Chris Wingard'
__license__ = 'Apache 2.0'

import numpy as np
from math import copysign

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, DatasetParserException
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey


class DataParticleType(BaseEnum):
    # Data particle types for the Open Ocean (aka Global) and Coastal gliders
    ### Global Gliders (GGLDR).
    GGLDR_CTDGV_DELAYED = 'ggldr_ctdpf_delyaed'
    GGLDR_CTDGV_RECOVERED = 'ggldr_ctdpf_recovered'
    GGLDR_FLORD_DELAYED = 'ggldr_flord_delayed'
    GGLDR_FLORD_RECOVERED = 'ggldr_flord_recovered'
    GGLDR_DOSTA_DELAYED = 'ggldr_dosta_delayed'
    GGLDR_DOSTA_RECOVERED = 'ggldr_dosta_recovered'
    GGLDR_GLDR_ENG_DELAYED = 'ggldr_eng_delayed'
    GGLDR_GLDR_ENG_RECOVERED = 'ggldr_eng_recovered'
    ### Coastal Gliders (CGLDR).
    CGLDR_CTDGV_DELAYED = 'cgldr_ctdpf_delyaed'
    CGLDR_CTDGV_RECOVERED = 'cgldr_ctdpf_recovered'
    CGLDR_FLORD_DELAYED = 'cgldr_flort_delayed'
    CGLDR_FLORD_RECOVERED = 'cgldr_flort_recovered'
    CGLDR_DOSTA_DELAYED = 'cgldr_dosta_delayed'
    CGLDR_DOSTA_RECOVERED = 'cgldr_dosta_recovered'
    CGLDR_PARAD_DELAYED = 'cgldr_parad_delayed'
    CGLDR_PARAD_RECOVERED = 'cgldr_parad_recovered'
    CGLDR_GLDR_ENG_DELAYED = 'cgldr_eng_delayed'
    CGLDR_GLDR_ENG_RECOVERED = 'cgldr_eng_recovered'

# [TODO: Build Particle classes for global recovered datasets and for all coastal glider data (delayed and recoverd)]

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
        Takes a GliderParser object and extracts CTD data from the
        data dictionary and puts the data into a CTD Data Particle.

        @param gpd A GliderParser class instance.
        @param result A returned list with sub dictionaries of the data
        """
        if not isinstance(gpd, GliderParser):
            raise SampleException("GGLDR_CTDGV_DELAYED: Object Instance is not a Glider Parsed Data object")

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
                        value = self._string_to_ddegrees(value)
                    else:
                        # otherwise store the values as floats
                        value = float(value)

                    # add the value to the record
                    record.append({DataParticleKey.VALUE_ID: key,
                                   DataParticleKey.VALUE: value})

                else:
                    log.warn("GGLDR_CTDGV_DELAYED: The defined particle, %s, is not \
                             present in the current data set", key)

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
        Takes a GliderParser object and extracts CTD data from the
        data dictionary and puts the data into a CTD Data Particle.

        @param gpd A GliderParser class instance.
        @param result A returned list with sub dictionaries of the data
        """
        if not isinstance(gpd, GliderParser):
            raise SampleException("GGLDR_DOSTA_DELAYED: Object Instance is not a GliderParser object")

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
                        value = self._string_to_ddegrees(value)
                    else:
                        # otherwise store the values as floats
                        value = float(value)

                    # add the value to the record
                    record.append({DataParticleKey.VALUE_ID: key,
                                   DataParticleKey.VALUE: value})

                else:
                    log.warn("GGLDR_DOSTA_DELAYED: The defined particle, %s, is not \
                             present in the current data set", key)

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
            raise SampleException("GGLDR_FLORD_DELAYED: Object Instance is not a GliderParser object")

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
                        value = self._string_to_ddegrees(value)
                    else:
                        # otherwise store the values as floats
                        value = float(value)

                    # add the value to the record
                    record.append({DataParticleKey.VALUE_ID: key,
                                   DataParticleKey.VALUE: value})

                else:
                    log.warn("GGLDR_FLORD_DELAYED: The defined particle, %s, is not \
                             present in the current data set", key)

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
            raise SampleException("GGLDR_ENG_DELAYED: Object Instance is not a GliderParser object")

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

                    # check to see if this is a lat/longitude string
                    if '_lat' in key or '_lon' in key:
                        # convert latitiude/longitude strings to decimal degrees
                        value = self._string_to_ddegrees(value)
                    else:
                        # otherwise store the values as floats
                        value = float(value)

                    # add the value to the record
                    record.append({DataParticleKey.VALUE_ID: key,
                                   DataParticleKey.VALUE: value})

                else:
                    log.warn("GGLDR_ENG_DELAYED: The defined particle, %s, is not \
                             present in the current data set", key)

            # add the record to total results
            result.append(record)

        return result


class GliderParser(object):
    """
    A class that parses a glider data file and holds the resultant data in
    dictionaries.

    GliderParser parses a Slocum Electric Glider data file that has been
    converted to ASCII from binary and merged with it's corresponding flight or
    science data file, and holds the self describing header data in a header
    dictionary and the data in a data dictionary using the column labels as the
    dictionary keys.

    Construct an instance of GliderParser using the filename of the
    ASCII file containing the glider data. For example:

        gdata = GliderParser('glider_data_file.mrg')

    * gdata.hdr_dict holds the header dictionary with the self
    describing ASCII tags from the file as keys.
    * gdata.data_dict holds a data dictionary with the variable names (column
    labels) as keys (gdata.data_keys) and the number of data records to parse
    (gdata.num_records).

    A sub-dictionary holds the name of the variable (same as the key),
    the data units, the number of binary bytes used to store each
    variable type, the name of the variable, and the data using the
    keys:
        'Name'
        'Units'
        'Number_of_Bytes'
        'Data'

    To retrieve the data for the variable 'vname':
        data = gdata.data_dict['vname]['Data']
    """

    def __init__(self, filename):
        self._fid = open(filename, 'r')
        self.hdr_dict = {}
        self.data_dict = {}
        self._read_header()
        self._read_data()
        self._fid.close()

    def _read_header(self):
        """
        Read in the self describing header lines of an ASCII glider data
        file.
        """
        # There are usually 14 header lines, start with 14,
        # and check the 'num_ascii_tags' line.
        num_hdr_lines = 14
        hdr_line = 1
        while hdr_line <= num_hdr_lines:
            line = self._fid.readline()
            split_line = line.split()
            if 'num_ascii_tags' in split_line:
                num_hdr_lines = int(split_line[1])
            self.hdr_dict[split_line[0][:-1]] = split_line[1]
            hdr_line += 1

    def _read_data(self):
        """
        Read in the column labels, data type, number of bytes of each
        data type, and the data from an ASCII glider data file.
        """
        column_labels = self._fid.readline().split()
        column_type = self._fid.readline().split()
        column_num_bytes = self._fid.readline().split()

        # read each row of data & use np.array's ability to grab a
        # column of an array
        data = []
        for line in self._fid.readlines():
            data.append(line.split())
        data_array = np.array(data)  # NOTE: this is an array of strings

        # warn if # of described data rows != to amount read in.
        num_columns = int(self.hdr_dict['sensors_per_cycle'])
        if num_columns != data_array.shape[1]:
            log.warn('Glider data file does not have the same' +
                     'number of columns as described in the header.\n' +
                     'Described: %d, Actual: %d' % (num_columns,
                                                    data_array.shape[1])
                     )

        # extract data to dictionary
        for ii in range(num_columns):
            self.data_dict[column_labels[ii]] = {
                'Name': column_labels[ii],
                'Units': column_type[ii],
                'Number_of_Bytes': int(column_num_bytes[ii]),
                'Data': data_array[:, ii]
            }
        self.data_keys = column_labels
        self.num_records = data_array.shape[0]

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
