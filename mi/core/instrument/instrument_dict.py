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
import pkg_resources
from mi.core.common import BaseEnum
from mi.core.exceptions import InstrumentParameterException

from mi.core.log import get_logger ; log = get_logger()

EGG_PATH = "resource"
DEFAULT_FILENAME = "strings.yml"

class InstrumentDict(object):
    """
    A package for classes that provides some base behavior for manages
    metadata and content for parameters, commands and drivers for the driver or
    protocol classes. 
    """
    
    @staticmethod
    def get_metadata_from_source(filename):
        """
        Load metadata from the given filename if it is there. If not, look for
        the default filename in the egg or development directory. Return the
        metadata as a structure.
        @param filename The file name to look in for YAML strings describing
        the dictionary.
        @retval the metadata structure as loaded by YAML
        @throw IOError if there is a problem opening the specified file
        """
        # if the file is in the default spot of the working path or egg, get that one       
        if (filename == None):
            resource_name = "%s/%s" % (EGG_PATH, DEFAULT_FILENAME)
            resource_base = __name__
            if not pkg_resources.resource_exists(resource_base, resource_name):
                # We are probably in a devel directory structure
                resource_name = "../%s/%s" % (EGG_PATH, DEFAULT_FILENAME)
                resource_base = "mi"
                log.debug("Attempting to load from devel dir with path %s", resource_name)
                if not pkg_resources.resource_exists(resource_base, resource_name):
                    return False # not in egg, not in devel dir
            else:
                log.debug("Attempting to load from egg with path %s", resource_name)
            yml = pkg_resources.resource_string(resource_base, resource_name)
            return yaml.load(yml)
    
        elif (filename != None):
            log.debug("Attempting to load parameter metadata from file %s",
                      filename)
            file = open("%s" % filename, "r")
            return yaml.safe_load(file)

        