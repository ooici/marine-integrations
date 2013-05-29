#!/usr/bin/env python

"""
@package mi.core.instrument.data_particle_generator Base data particle generator
@file mi/core/instrument/data_particle_generator.py
@author Steve Foley
@brief Contains logic to generate data particles to be exchanged between
the driver and agent. This involves a JSON interchange format
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import time
import copy
import ntplib
import base64
import logging
from warnings import warn
try:
    import simplejson as json
except ImportError:
    warn("Failed to import simplejson; particle generation will be slower.")
    import json

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, ReadOnlyException, NotImplementedException, InstrumentParameterException
from mi.core.log import get_logger ; log = get_logger()

class CommonDataParticleType(BaseEnum):
    """
    This enum defines all the common particle types defined in the modules.  Currently there is only one, but by
    using an enum here we have the opportunity to define more common data particles.
    """
    RAW = "raw"

class DataParticleKey(BaseEnum):
    PKT_FORMAT_ID = "pkt_format_id"
    PKT_VERSION = "pkt_version"
    STREAM_NAME = "stream_name"
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

    # data particle type is intended to be defined in each derived data particle class.  This value should be unique
    # for all data particles.  Best practice is to access this variable using the accessor method:
    # data_particle_type()
    _data_particle_type = None

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK):
        """ Build a particle seeded with appropriate information
        
        @param raw_data The raw data used in the particle
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
        self.raw_data = raw_data

    def set_internal_timestamp(self, timestamp=None, unix_time=None):
        """
        Set the internal timestamp
        @param timestamp: NTP timestamp to set
        @param unit_time: Unix time as returned from time.time()
        @raise InstrumentParameterException if timestamp or unix_time not supplied
        """
        if(timestamp == None and unix_time == None):
            raise InstrumentParameterException("timestamp or unix_time required")

        if(unix_time != None):
            timestamp = ntplib.system_to_ntp_time(unix_time)

        # Do we want this to happen here or in down stream processes?
        #if(not self._check_timestamp(timestamp)):
        #    raise InstrumentParameterException("invalid timestamp")

        self.contents[DataParticleKey.INTERNAL_TIMESTAMP] = float(timestamp)

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
        

    def data_particle_type(self):
        """
        Return the data particle type (aka stream name)
        @raise: NotImplementedException if _data_particle_type is not set
        """
        if(self._data_particle_type == None):
            raise NotImplementedException("_data_particle_type not initialized")

        return self._data_particle_type

    def generate(self):
        """
        Generates a JSON_parsed packet from a sample dictionary of sensor data and
        associates a timestamp with it
        
        @param portagent_time The timestamp from the instrument in NTP binary format 
        @param data The actual data being sent in raw byte[] format
        @return A JSON_raw string, properly structured with port agent time stamp
           and driver timestamp
        @throws InstrumentDriverException If there is a problem with the inputs
        """
        # Do we wan't downstream processes to check this?
        #for time in [DataParticleKey.INTERNAL_TIMESTAMP,
        #             DataParticleKey.DRIVER_TIMESTAMP,
        #             DataParticleKey.PORT_TIMESTAMP]:
        #    if  not self._check_timestamp(self.contents[time]):
        #        raise SampleException("Invalid port agent timestamp in raw packet")

        # verify preferred timestamp exists in the structure...
        if not self._check_preferred_timestamps():
            raise SampleException("Preferred timestamp not in particle!")
        
        # build response structure
        values = self._build_parsed_values()
        result = self._build_base_structure()
        result[DataParticleKey.STREAM_NAME] = self.data_particle_type()
        result[DataParticleKey.VALUES] = values

        log.debug("Serialize result: %s" % result)

        # JSONify response, sorting is nice for testing
        # But sorting is awfully slow
        json_result = json.dumps(result, sort_keys=False)
        
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
        result = dict(self.contents)
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

        # This should be handled downstream.  Don't want to not publish data because
        # the port agent stopped putting out timestamps
        #if self.contents[self.contents[DataParticleKey.PREFERRED_TIMESTAMP]] == None:
        #    raise SampleException("Preferred timestamp, %s, is not defined" %
        #                          self.contents[DataParticleKey.PREFERRED_TIMESTAMP])
        
        return True

class RawDataParticleKey(BaseEnum):
    PAYLOAD = "raw"
    LENGTH = "length"
    TYPE = "type"
    CHECKSUM = "checksum"

class RawDataParticle(DataParticle):
    """
    This class a common data particle for generating data particles of raw
    data.

    It essentially is a translation of the port agent packet
    """
    _data_particle_type = CommonDataParticleType.RAW

    def _build_parsed_values(self):
        """
        Build a particle out of a port agent packet.
        @returns A list that is ready to be added to the "values" tag before
           the structure is JSONified
        """

        port_agent_packet = self.raw_data
        if(not isinstance(port_agent_packet, dict)):
            raise SampleException("raw data not a dictionary")

        for param in ["raw", "length", "type", "checksum"]:
             if(not param in port_agent_packet.keys()):
                  raise SampleException("raw data not a complete port agent packet. missing %s" % param)


        payload = None
        length = None
        type = None
        checksum = None

        # Attempt to convert values
        try: 
            payload = base64.b64encode(port_agent_packet.get("raw"))
        except TypeError:
            pass

        try: 
            length = int(port_agent_packet.get("length"))
        except TypeError: 
            pass

        try: 
            type = int(port_agent_packet.get("type"))
        except TypeError: 
            pass

        try: 
            checksum = int(port_agent_packet.get("checksum"))
        except TypeError: 
            pass

        result = [{
                      DataParticleKey.VALUE_ID: RawDataParticleKey.PAYLOAD,
                      DataParticleKey.VALUE: payload,
                      DataParticleKey.BINARY: True},
                  {
                      DataParticleKey.VALUE_ID: RawDataParticleKey.LENGTH,
                      DataParticleKey.VALUE: length},
                  {
                      DataParticleKey.VALUE_ID: RawDataParticleKey.TYPE,
                      DataParticleKey.VALUE: type},
                  {
                      DataParticleKey.VALUE_ID: RawDataParticleKey.CHECKSUM,
                      DataParticleKey.VALUE: checksum},
        ]

        return result
