#!/usr/bin/env python

"""
@package mi.core.instrument.data_particle_generator Base data particle generator
@file mi/core/instrument/data_particle_generator.py
@author Steve Foley
@brief Contains logic to generate data particles to be exchanged between
the driver and agent. This involves a JSON interchange format, raw vs parsed
formats, etc.
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import time
import copy
import ntplib
import base64
import json

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, ReadOnlyException, NotImplementedException
from mi.core.log import get_logger ; log = get_logger()

class DataParticleKey(BaseEnum):
    PKT_FORMAT_ID = "pkt_format_id"
    PKT_VERSION = "pkt_version"
    STREAM_NAME = "stream_name"
    INSTRUMENT_ID = "instrument_id"
    INTERNAL_TIMESTAMP = "internal_timestamp"
    PORT_TIMESTAMP = "port_timestamp"
    DRIVER_TIMESTAMP = "driver_timestamp"
    PREFERRED_TIMESTAMP = "preferred_timestamp"
    QUALITY_FLAG = "quality_flag"
    VALUES = "values"
    VALUE_ID = "value_id"
    VALUE = "value"
    BINARY = "binary"

class DataParticleValue(BaseEnum):
    JSON_DATA = "JSON_Data"
    RAW = "raw"
    PARSED = "parsed"
    ENG = "eng"
    OK = "ok"
    CHECKSUM_FAILED = "checksum_failed"
    OUT_OF_RANGE = "out_of_range"
    INVALID = "invalid"
    QUESTIONABLE = "questionable"
    
class DataParticle(object):
    """
    This class is responsible for storing and ultimately generating data
    particles in the designated format from the associated inputs. It
    fills in fields as necessary, and is a valid Data Particle
    that can be sent up to the InstrumentAgent.
    
    It is the intent that this class is subclassed as needed if an instrument must
    modify fields in the outgoing packet. The hope is to have most of the superclass
    code be called by the child class with just values overridden as needed.
    """

    def __init__(self, instrument_id, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK):
        """ Build a particle seeded with appropriate information
        
        @param instrument_id The the instrument id that the instrument
            is using in ION so we can build appropriate packets.
        @param raw_data The raw data used in the particle
        """
        self.contents = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.INSTRUMENT_ID: instrument_id,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.INTERNAL_TIMESTAMP: internal_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: ntplib.system_to_ntp_time(time.time()),
            DataParticleKey.PREFERRED_TIMESTAMP: preferred_timestamp,
            DataParticleKey.QUALITY_FLAG: quality_flag
        }
        self.raw_data = raw_data
    
    def set_value(self, id, value):
        """
        Set a content value, restricted as necessary
        
        @param id The ID of the value to set, should be from DataParticleKey
        @param value The value to set
        @raises ReadOnlyException If the parameter cannot be set
        """
        if (id == DataParticleKey.INTERNAL_TIMESTAMP) and (self._check_timestamp(value)):
            self.contents[DataParticleKey.INTERNAL_TIMESTAMP] = value
        else:
            raise ReadOnlyException("Parameter %s not able to be set to %s after object creation!" %
                                    (id, value))
    
    def get_value(self, id):
        """ Return a stored value
        
        @param id The ID (from DataParticleKey) for the parameter to return
        @raises NotImplementedException If there is an invalid id
        """
        if DataParticleKey.has(id):
            return self.contents[id]
        else:
            raise NotImplementedException("Value %s not available in particle!", id)
        
    def generate_raw(self):
        """
        Generates a JSON packet from raw bytes of sensor data and associates a
        timestamp with it
        
        @return A JSON_raw string, properly structured with port agent time stamp
           and driver timestamp
        @throws SampleException If there is a problem with the inputs
        """
        for time in [DataParticleKey.INTERNAL_TIMESTAMP,
                     DataParticleKey.DRIVER_TIMESTAMP,
                     DataParticleKey.PORT_TIMESTAMP]:
            if  not self._check_timestamp(self.contents[time]):
                raise SampleException("Invalid port agent timestamp in raw packet")

        # verify preferred timestamp exists in the structure...
        if not self._check_preferred_timestamps():
            raise SampleException("Preferred timestamp, %s, not in particle!" %
                                  self.contents[DataParticleKey.PREFERRED_TIMESTAMP])
        
        # build response structure
        result = self._build_base_structure()
        result[DataParticleKey.STREAM_NAME] = DataParticleValue.RAW
        result[DataParticleKey.VALUES] = self._build_raw_values()
        
        # JSONify response, sorting is nice for testing
        json_result = json.dumps(result, sort_keys=True)
        
        # return result
        return json_result
        
    def _build_raw_values(self):
        """
        Build just the values list for a raw data structure. This will be
        added to the "values" tag in the JSON structure. Just the structure
        is built so that a child class can override this class, but call it
        with super() to get the base structure before modification
        
        @returns A list that is ready to be added to the "values" tag before
           the structure is JSONified
        """
        result = [{
            DataParticleKey.VALUE_ID: DataParticleValue.RAW,
            DataParticleKey.VALUE: base64.b64encode(self.raw_data),
            DataParticleKey.BINARY: True}]

        return result
        
    def generate_parsed(self):
        """
        Generates a JSON_parsed packet from a sample dictionary of sensor data and
        associates a timestamp with it
        
        @param portagent_time The timestamp from the instrument in NTP binary format 
        @param data The actual data being sent in raw byte[] format
        @return A JSON_raw string, properly structured with port agent time stamp
           and driver timestamp
        @throws InstrumentDriverException If there is a problem with the inputs
        """
        for time in [DataParticleKey.INTERNAL_TIMESTAMP,
                     DataParticleKey.DRIVER_TIMESTAMP,
                     DataParticleKey.PORT_TIMESTAMP]:
            if  not self._check_timestamp(self.contents[time]):
                raise SampleException("Invalid port agent timestamp in raw packet")

        # verify preferred timestamp exists in the structure...
        if not self._check_preferred_timestamps():
            raise SampleException("Preferred timestamp not in particle!")
        
        # build response structure
        result = self._build_base_structure()
        result[DataParticleKey.STREAM_NAME] = DataParticleValue.PARSED
        result[DataParticleKey.VALUES] = self._build_parsed_values()
        
        # JSONify response, sorting is nice for testing
        json_result = json.dumps(result, sort_keys=True)
        
        # return result
        return json_result
        
    def _build_parsed_values(self):
        """
        Build values of a parsed structure. Just the values are built so
        so that a child class can override this class, but call it with
        super() to get the base structure before modification
        
        @return the values tag for this data structure ready to JSONify
        @raises SampleException when parsed values can not be properly returned
        """
        raise SampleException("Parsed values block not overridden")


    def _build_base_structure(self):
        """
        Build the base/header information for an output structure.
        Follow on methods can then modify it by adding or editing values.
        
        @return A fresh copy of a core structure to be exported
        """
        # set the driver time
        driver_time = ntplib.system_to_ntp_time(time.time())
        result = {}
        result[DataParticleKey.DRIVER_TIMESTAMP] = driver_time
        
        result = copy.deepcopy(self.contents)
        # clean out optional fields that were missing
        if not self.contents[DataParticleKey.PORT_TIMESTAMP]:
            del result[DataParticleKey.PORT_TIMESTAMP]
        if not self.contents[DataParticleKey.INTERNAL_TIMESTAMP]:
            del result[DataParticleKey.INTERNAL_TIMESTAMP]
        return result
    
    def _check_timestamp(self, timestamp):
        """
        Check to make sure the timestamp is reasonable
        
        @param timestamp An NTP4 formatted timestamp (64bit)
        @return True if timestamp is okay or None, False otherwise
        """
        if timestamp == None:
            return True
        if not isinstance(timestamp, float):
            return False
        
        # is it sufficiently in the future to be unreasonable?
        if timestamp > ntplib.system_to_ntp_time(time.time()+(86400*365)):
            return False
        else:
            return True
    
    def _check_preferred_timestamps(self):
        """
        Check to make sure the preferred timestamp indicated in the
        particle is actually listed, possibly adjusting to 2nd best
        if not there.
        
        @throws SampleException When there is a problem with the preferred
            timestamp in the sample.
        """        
        if self.contents[DataParticleKey.PREFERRED_TIMESTAMP] == None:
            raise SampleException("Missing preferred timestamp, %s, in particle" %
                                  self.contents[DataParticleKey.PREFERRED_TIMESTAMP])
        if self.contents[self.contents[DataParticleKey.PREFERRED_TIMESTAMP]] == None:
            raise SampleException("Preferred timestamp, %s, is not defined" %
                                  self.contents[DataParticleKey.PREFERRED_TIMESTAMP])
        
        return True