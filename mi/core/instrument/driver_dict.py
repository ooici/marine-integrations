#!/usr/bin/env python

"""
@package ion.services.mi.driver_dict
@file ion/services/mi/driver_dict.py
@author Steve Foley
@brief A dictionary class that manages metadata about the driver itself, most
likely to return to the agent and up the chain to the UI.
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum

from mi.core.instrument.instrument_dict import InstrumentDict
from mi.core.log import get_logger ; log = get_logger()

class DriverDictKey(BaseEnum):
    DRIVER = "driver"
    VENDOR_SW_COMPATIBLE = "vendor_sw_compatible"
    
class DriverDict(InstrumentDict):
    """
    Driver metadata dictionary. Collects driver information for use later
    in generating a command/parameter/driver JSON object for the UI.
    """
    def __init__(self):
        """
        Constructor.        
        """
        self._driver_dict = {}
        
    def add(self, name, value=None):
        """
        Add or replace a name/value to the driver dictionary.
        @param name The name of the name/value pair.
        @param value The value of the name/value pair.
        """      
        self._driver_dict[name] = value
        
    def get_value(self, name):
        """
        Get the value by name.
        @param name The name of the value to retreive
        @retval The value associated with the command
        @throw KeyError if no value exists
        """
        if (name == None) or (name not in self._driver_dict.keys()):
            raise KeyError("Invalid name: %s" % name)
                    
        return self._driver_dict[name]
        
    def generate_dict(self):
        """
        Generate a JSONify-able metadata schema that describes the values.
        This could be passed up toward the agent for ultimate handing to the UI.
        This method only handles the driver block of the schema.
        """        
        return self._driver_dict
            
        
        