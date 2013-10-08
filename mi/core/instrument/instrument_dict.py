#!/usr/bin/env python

"""
@package mi.core.instrument.instrument_dict
@file mi/core/instrument/instrument_dict.py
@author Steve Foley
@brief A package for classes that provides some base behavior for manages
metadata and content for parameters, commands and drivers for the driver or
protocol classes.
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import yaml
import sys
import pkg_resources
from mi.core.common import BaseEnum
from mi.core.exceptions import InstrumentParameterException

from mi.core.log import get_logger ; log = get_logger()

MODULE = "res"
EGG_PATH = "config"
DEFAULT_FILENAME = "strings.yml"

class InstrumentDict(object):
    """
    A package for classes that provides some base behavior for manages
    metadata and content for parameters, commands and drivers for the driver or
    protocol classes. 
    """
    
    @staticmethod
    def load_metadata_from_file(filename):
        log.debug("Attempting to load instrument dictionary metadata from file %s",
                      filename)
        file = open("%s" % filename, "r")
        return yaml.safe_load(file)
        
    @staticmethod
    def load_metadata_from_egg():
        try:
            import res
        except ImportError:
            return False
        
        resource_name = "%s/%s" % (EGG_PATH, DEFAULT_FILENAME)
        resource_base = "res"
        log.debug("Attempting to load instrument dictionary metadata from egg with path %s, base %s",
                  resource_name, resource_base)
        if pkg_resources.resource_exists(resource_base, resource_name):
            yml = pkg_resources.resource_string(resource_base, resource_name)
            log.debug("Found resource in the %s, %s base",
                      resource_base, resource_name)
            return yaml.load(yml)
        else:
            return False
    
    @staticmethod
    def get_metadata_from_source(devel_path=None, filename=None):
        """
        Load metadata from a specific file if included. If not specified,
        try looking for where it would be in an egg. If not there, look in the
        specified place withindevelopment environment.
        
        @param filename The file name to look in for YAML strings describing
        the dictionary should it be in a random location.
        @param devel_path The path where the file can be found during development.
        This is likely in the mi/instrument/make/model/flavor/resource directory.
        Include a filename for this argument.
        @retval the metadata structure as loaded by YAML, None if no metadata successfully
        loaded
        @throw IOError if there is a problem opening the specified file
        """
        if filename:
            return InstrumentDict.load_metadata_from_file(filename)     
            
        if devel_path:
            result = InstrumentDict.load_metadata_from_file(devel_path)
            if result:
                return result        

        result = InstrumentDict.load_metadata_from_egg()     
        if result:
            return result
                            
        log.debug("No external instrument dictionary metadata found, using hard coded values.")
        return None

        