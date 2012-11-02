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

from mi.core.log import get_logger ; log = get_logger()

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
                 submenu_write=None,
                 multi_match=False,
                 direct_access=False,
                 startup_param=False,
                 default_value=None,
                 init_value=None):
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
        self.multi_match = multi_match
        self.direct_access = direct_access
        self.startup_param = startup_param
        self.default_value = default_value
        self.init_value = init_value

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
            mi_logger.debug('self.value = ' + str(self.value))

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
        self._param_dict = {}
        
    def add(self, name, pattern, f_getval, f_format, value=None,
            visibility=ParameterDictVisibility.READ_WRITE,
            menu_path_read=None, submenu_read=None,
            menu_path_write=None, submenu_write=None,
            multi_match=False, direct_access=False, startup_param=False,
            default_value=None, init_value=None):
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
        @param direct_access T/F for tagging this as a direct access parameter
        to be saved and restored in and out of direct access
        @param startup_param T/F for tagging this as a startup parameter to be
        applied when the instrument is first configured
        @param default_value The default value to use for this parameter when
        a value is needed, but no other instructions have been provided.
        @param init_value The value that a parameter should be set to during
        initialization or re-initialization
        @param value The parameter value (initializes to None).        
        """
        val = ParameterDictVal(name, pattern, f_getval, f_format,
                               value=value,
                               visibility=visibility,
                               menu_path_read=menu_path_read,
                               submenu_read=submenu_read,
                               menu_path_write=menu_path_write,
                               submenu_write=submenu_write,
                               multi_match=multi_match,
                               direct_access=direct_access,
                               startup_param=startup_param,
                               default_value=default_value,
                               init_value=init_value)
        self._param_dict[name] = val
        
    def get(self, name):
        """
        Get a parameter value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        """
        return self._param_dict[name].value
        
    def get_init_value(self, name):
        """
        Get a parameter's init value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        """
        return self._param_dict[name].init_value

    def get_default_value(self, name):
        """
        Get a parameter's default value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        """
        return self._param_dict[name].default_value
    
    def set(self, name, value):
        """
        Set a parameter value in the dictionary.
        @param name The parameter name.
        @param value The parameter value.
        @raises KeyError if the name is invalid.
        """
        log.debug("setting " + name + " to " + str(value))
        self._param_dict[name] = value
        
    def set_default(self, name):
        """
        Set the value to the default value stored in the param dict
        @raise KeyError if the name is invalid
        @raise ValueError if the default_value is missing
        """
        if self._param_dict[name].default_value:
            self._param_dict[name].value = self._param_dict[name].default_value
        else:
            raise ValueError("Missing default value")
            
    def set_init_value(self, name, value):
        """
        Set the value to the default value stored in the param dict
        @param The parameter name to add to
        @param The value to set for the initialization variable
        @raise KeyError if the name is invalid
        """
        self._param_dict[name].init_value = value
        
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

    # RAU Added
    def multi_match_update(self, input):
        """
        Update the dictionaray with a line input. Iterate through all objects
        and attempt to match and update (a) parameter(s).
        @param input A string to match to a dictionary object.
        @retval The count of successfully updated parameters, 0 if not updated
        """
        hit_count = 0
        multi_mode = False
        for (name, val) in self._param_dict.iteritems():
            if multi_mode == True and val.multi_match == False:
                continue
            if val.update(input):
                hit_count =hit_count +1
                if False == val.multi_match:
                    return hit_count
                else:
                    multi_mode = True

        if False == multi_mode and input <> "":
            log.debug("protocol_param_dict.py UNMATCHCHED ***************************** " + input)
        return hit_count

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

    def get_direct_access_list(self):
        """
        Return a list of parameter names that are tagged as direct access
        parameters
        
        @retval A list of parameter names, possibly empty
        """
        return_val = []
        for key in self._param_dict.keys():
            if self._param_dict[key].direct_access == True:
                return_val.append(key)
        
        return return_val
        
    def get_startup_list(self):
        """
        Return a list of parameter names that are tagged as startup parameters
        
        @retval A list of parameter names, possibly empty
        """
        return_val = []
        for key in self._param_dict.keys():
            if self._param_dict[key].startup_param == True:
                return_val.append(key)
        
        return return_val
    