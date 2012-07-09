#!/usr/bin/env python

"""
@package ion.services.mi.protocol_param_dict
@file ion/services/mi/protocol_param_dict.py
@author Edward Hunter
@brief A dictionary class that manages, matches and formats device parameters.
"""

__author__ = 'Edward Hunter'
__license__ = 'Apache 2.0'

import re
import logging
from mi.core.common import BaseEnum

mi_logger = logging.getLogger('mi_logger')

class ParameterDictVisibility(BaseEnum):
    READ_ONLY = "READ_ONLY"
    READ_WRITE = "READ_WRITE"
    DIRECT_ACCESS = "DIRECT_ACCESS"

class ParameterDictVal(object):
    """
    A parameter dictionary value.
    """
    """
    def __init__(self, name, pattern, f_getval, f_format, value=None,
                 visibility=ParameterDictVisibility.READ_WRITE,
                 menu_path_read=None,
                 menu_path_write=None):
    """
    def __init__(self, name, pattern, f_getval, f_format, value=None,
                 visibility=ParameterDictVisibility.READ_WRITE,
                 menu_path_read=None,
                 submenu_read=None,
                 menu_path_write=None,
                 submenu_write=None):
        """
        Parameter value constructor.
        @param name The parameter name.
        @param pattern The regex that matches the parameter in line output.
        @param f_getval The fuction that extracts the value from a regex match.
        @param f_format The function that formats the parameter value for a set command.
        @param visibility The ParameterDictVisibility value that indicates what
        the access to this parameter is
        @param menu_path The path of menu options required to get to the parameter
        value display when presented in a menu-based instrument
        @param value The parameter value (initializes to None).
        """
        self.name = name
        self.pattern = pattern
        self.regex = re.compile(pattern)
        self.f_getval = f_getval
        self.f_format = f_format
        self.value = value
        self.menu_path_read = menu_path_read
        self.submenu_read = submenu_read
        self.menu_path_write = menu_path_write
        self.submenu_write = submenu_write
        self.visibility = visibility

    def update(self, input):
        """
        Attempt to udpate a parameter value. If the input string matches the
        value regex, extract and update the dictionary value.
        @param input A string possibly containing the parameter value.
        @retval True if an update was successful, False otherwise.
        """
        match = self.regex.match(input)
        if match:
            self.value = self.f_getval(match)
            mi_logger.debug('Updated parameter %s=%s', self.name, str(self.value))
            return True
        else:
            return False


class ProtocolParameterDict(object):
    """
    Protocol parameter dictionary. Manages, matches and formats device
    parameters.
    """
    def __init__(self):
        """
        Constructor.        
        """
        self._param_dict= {}
        
    """
    def add(self, name, pattern, f_getval, f_format, value=None,
            visibility=ParameterDictVisibility.READ_WRITE,
            menu_path_read=None, menu_path_write=None):
    """
    def add(self, name, pattern, f_getval, f_format, value=None,
            visibility=ParameterDictVisibility.READ_WRITE,
            menu_path_read=None, submenu_read=None,
            menu_path_write=None, submenu_write=None):
        """
        Add a parameter object to the dictionary.
        @param name The parameter name.
        @param pattern The regex that matches the parameter in line output.
        @param f_getval The fuction that extracts the value from a regex match.
        @param f_format The function that formats the parameter value for a set command.
        @param visibility The ParameterDictVisibility value that indicates what
        the access to this parameter is
        @param menu_path The path of menu options required to get to the parameter
        value display when presented in a menu-based instrument
        @param value The parameter value (initializes to None).        
        """
        val = ParameterDictVal(name, pattern, f_getval, f_format,
                               value=value,
                               visibility=visibility,
                               menu_path_read=menu_path_read,
                               submenu_read=submenu_read,
                               menu_path_write=menu_path_write,
                               submenu_write=submenu_write)
        self._param_dict[name] = val
        
    def get(self, name):
        """
        Get a parameter value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        """
        return self._param_dict[name].value
        
    def set(self, name, value):
        """
        Set a parameter value in the dictionary.
        @param name The parameter name.
        @param value The parameter value.
        @raises KeyError if the name is invalid.
        """
        self._param_dict[name] = value
        
    # DHE Added
    def get_menu_path_read(self, name):
        """
        Get a parameter value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        """
        return self._param_dict[name].menu_path_read
        
    # DHE Added
    # This is the final destination submenu
    def get_submenu_read(self, name):
        """
        Get a parameter value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        """
        return self._param_dict[name].submenu_read
        
    # DHE Added
    def get_menu_path_write(self, name):
        """
        Get a parameter value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        """
        return self._param_dict[name].menu_path_write
        
    # DHE Added
    # This is the final destination submenu
    def get_submenu_write(self, name):
        """
        Get a parameter value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        """
        return self._param_dict[name].submenu_write
        
    def update(self, input):
        """
        Update the dictionaray with a line input. Iterate through all objects
        and attempt to match and update a parameter.
        @param input A string to match to a dictionary object.
        @retval The name that was successfully updated, None if not updated
        """
        for (name, val) in self._param_dict.iteritems():
            if val.update(input):
                return name
        return False
    
    def get_config(self):
        """
        Retrive the configuration (all key values).
        @retval name : value configuration dict.
        """
        config = {}
        for (key, val) in self._param_dict.iteritems():
            config[key] = val.value
        return config
    
    def format(self, name, val):
        """
        Format a parameter for a set command.
        @param name The name of the parameter.
        @param val The parameter value.
        @retval The value formatted as a string for writing to the device.
        @raises InstrumentProtocolException if the value could not be formatted.
        @raises KeyError if the parameter name is invalid.
        """
        return self._param_dict[name].f_format(val)
        
    def get_keys(self):
        """
        Return list of all parameter names in the dictionary.
        """
        return self._param_dict.keys()

        
