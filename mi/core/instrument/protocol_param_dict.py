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
from mi.core.common import BaseEnum
from mi.core.exceptions import InstrumentParameterException

from mi.core.log import get_logger ; log = get_logger()

class ParameterDictVisibility(BaseEnum):
    READ_ONLY = "READ_ONLY"
    READ_WRITE = "READ_WRITE"
    DIRECT_ACCESS = "DIRECT_ACCESS"

class ParameterDictVal(object):
    """
    A parameter dictionary value.
    """
    def __init__(self, name, f_format, value=None,
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
        @param f_format The function that formats the parameter value for a set command.
        @param visibility The ParameterDictVisibility value that indicates what
        the access to this parameter is
        @param menu_path The path of menu options required to get to the parameter
        value display when presented in a menu-based instrument
        @param value The parameter value (initializes to None).
        """
        self.name = name
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
        Attempt to udpate a parameter value. By default, this assumes the input
        will be new new value. In subclasses, this must be updated to handle
        a real string of data appropriately.
        @param input A string that is the parameter value.
        @retval True if an update was successful, False otherwise.
        """
        self.value = input
        return True
    
class RegexParamDictVal(ParameterDictVal):
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
        ParameterDictVal.__init__(self,
                                  name,
                                  f_format,
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

        self.pattern = pattern
        self.regex = re.compile(pattern)
        self.f_getval = f_getval

    def update(self, input):
        """
        Attempt to udpate a parameter value. If the input string matches the
        value regex, extract and update the dictionary value.
        @param input A string possibly containing the parameter value.
        @retval True if an update was successful, False otherwise.
        """
        if not (isinstance(input, str)):
            match = self.regex.search(str(input))
        else:
            match = self.regex.search(input)

        if match:
            self.value = self.f_getval(match)
            log.trace('Updated parameter %s=%s', self.name, str(self.value))

            return True
        else:
            return False
        
class FunctionParamDictVal(ParameterDictVal):
    def __init__(self, name, f_getval, f_format, value=None,
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
        @param f_getval The fuction that extracts the value from a regex match.
        If no value is found for extraction, this function should return
        something false.
        @param f_format The function that formats the parameter value for a set command.
        @param visibility The ParameterDictVisibility value that indicates what
        the access to this parameter is
        @param menu_path The path of menu options required to get to the parameter
        value display when presented in a menu-based instrument
        @param value The parameter value (initializes to None).
        """
        ParameterDictVal.__init__(self,
                                  name,
                                  f_format,
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

        self.f_getval = f_getval

    def update(self, input):
        """
        Attempt to udpate a parameter value. The input string is run through
        the filtering function to obtain a value.
        @param input A string possibly containing the parameter value in some
        format.
        @retval True if a change was made to the value, false if the value is
        the same as it was before. Since the result of the supplied function
        could be anything (boolean included), there isnt any way to tell the
        success or failure of the match...all update methods run. The result
        is a change flag.
        """
        orig_value = self.value
        result = self.f_getval(input)
        if result != orig_value:
            self.value = result
            log.trace('self.value = ' + str(self.value))
            log.trace('Updated parameter %s=%s', self.name, str(self.value))
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
        Add a parameter object to the dictionary using a regex for extraction.
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
        val = RegexParamDictVal(name, pattern, f_getval, f_format,
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

    def add_paramdictval(self, pdv):
        """
        Add a ParameterDictVal object to the dictionary. The value can be
        any object that is an instance of the ParameterDictVal class or
        subclasses. This is the preferred method for adding these entries as
        they allow the user to choose the type of param dict val to be used
        and make testing more straightforward.
        @param pdv The ParameterDictVal to use
        """
        if not (isinstance(pdv, ParameterDictVal)):
            raise InstrumentParameterException(
                "Invalid ParameterDictVal added! Attempting to add: %s" % pdv)
        self._param_dict[pdv.name] = pdv
        
    def get(self, name):
        """
        Get a parameter value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        """
        return self._param_dict[name].value

    def get_config_value(self, name):
        """
        Get a parameter's startup configuration value based on a search
        priority.
        1. User initialization value
        2. Driver default value
        3. Current value if set via update method
        4. None if no value could be determined
        @param name Name of the value to be retrieved.
        @return A startup configuration value if one could be found
                otherwise None
        @raises KeyError if the name is invalid.
        """
        result = self.get_init_value(name)
        if result != None:
            log.trace("Got init value for %s: %s", name, result)
            return result

        result = self.get_default_value(name)
        if result != None:
            log.trace("Got default value for %s: %s", name, result)
            return result

        # Currently we don't have a way to determine if a value was
        # set explicitly or via some data handler. The updated flag
        # doesn't work because the update method is called in both
        # instances
        # result = self.get(name)
        #if result != None and self._param_dict[name].updated == True:
        #    log.trace("Got current value for %s: %s", name, result)
        #    return result

        return None

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

    def update_many(self, input):
        """
        Take in multiple inputs and update many parameters at once.
        @param input a line or lines of input to parse
        @retval A dict with the names and values that were updated
        """
        result = {}
        for (name, val) in self._param_dict.iteritems():
            update_result = val.update(input)
            if update_result:
                result[name] = update_result 
        return result

    def update(self, input):
        """
        Update the dictionaray with a line input. Iterate through all objects
        and attempt to match and update a parameter. Only updates the first
        match encountered.
        @param input A string to match to a dictionary object.
        @retval The name that was successfully updated, None if not updated
        """
        log.debug("update input: %s" % input)
        found = False
        for (name, val) in self._param_dict.iteritems():
            log.trace("update param dict name: %s" % name)
            if val.update(input):
                found = True
        return found
    
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

    def is_startup_param(self, name):
        """
        Return true if a parameter name references a startup parameter
        @param name: name of a parameter
        @return: True if the parameter is flagged as a startup param
        @raise: KeyError if parameter doesn't exist
        """
        return self._param_dict[name].startup_param == True

    def get_startup_list(self):
        """
        Return a list of parameter names that are tagged as startup parameters
        
        @retval A list of parameter names, possibly empty
        """
        return_val = []
        for key in self._param_dict.keys():
            if self.is_startup_param(key):
                return_val.append(key)
        
        return return_val
    
    def get_visibility_list(self, visibility):
        """
        Return a list of parameter names that are tagged with the given
        visibility
        
        @param visability A value from the ParameterDictVisibility enum
        @retval A list of parameter names, possibly empty
        """
        return_val = []
        
        for key in self._param_dict.keys():
            if self._param_dict[key].visibility == visibility:
                return_val.append(key)
        
        return return_val
    