#!/usr/bin/env python

"""
@package mi.core.instrument.protocol_param_dict
@file mi/core/instrument/protocol_param_dict.py
@author Edward Hunter
@author Steve Foley
@brief A dictionary class that manages, matches and formats device parameters.
"""

__author__ = 'Edward Hunter'
__license__ = 'Apache 2.0'

import re
import ntplib
import time
import yaml
import pkg_resources

from mi.core.common import BaseEnum
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentParameterExpirationException
from mi.core.instrument.instrument_dict import InstrumentDict

from mi.core.log import get_logger ; log = get_logger()

EGG_PATH = "resource"
DEFAULT_FILENAME = "strings.yml"

class ParameterDictType(BaseEnum):
    BOOL = "bool"
    INT = "int"
    STRING = "string"
    FLOAT = "float"
    LIST = "list"
    BOOL = "bool"
    ENUM = "enum"

class ParameterDictVisibility(BaseEnum):
    READ_ONLY = "READ_ONLY"  # Can not be set by the driver at any time
    READ_WRITE = "READ_WRITE" # Can be set by the driver or the operator
    IMMUTABLE = "IMMUTABLE" # Can only be set by the driver during startup
    DIRECT_ACCESS = "DIRECT_ACCESS"
    
class ParameterDictKey(BaseEnum):
    """
    These are the output strings when generating a metadata block. They also
    line up with incoming YAML strings where appropriate.
    """
    GET_TIMEOUT = "get_timeout"
    SET_TIMEOUT = "set_timeout"
    VISIBILITY = "visibility"
    STARTUP = "startup"
    DIRECT_ACCESS = "direct_access"
    DISPLAY_NAME = "display_name"
    DESCRIPTION = "description"
    VALUE = "value"
    TYPE = "type"
    DEFAULT = "default"
    UNITS = "units"
    PARAMETERS = "parameters"
    VALUE_DESCRIPTION = "value_description"
    
class ParameterDescription(object):
    """
    An object handling the descriptive (and largely staticly defined in code)
    qualities of a parameter.
    """
    def __init__(self,
                 name,
                 visibility=ParameterDictVisibility.READ_WRITE,
                 direct_access=False,
                 startup_param=False,
                 default_value=None,
                 init_value=None,
                 menu_path_read=None,
                 submenu_read=None,
                 menu_path_write=None,
                 submenu_write=None,
                 multi_match=None,
                 get_timeout=10,
                 set_timeout=10,
                 display_name=None,
                 description=None,
                 type=None,
                 units=None,
                 value_description=None):
        self.name = name
        self.visibility = visibility
        self.direct_access = direct_access
        self.startup_param = startup_param
        self.default_value = default_value
        self.init_value = init_value
        self.menu_path_read = menu_path_read
        self.submenu_read = submenu_read
        self.menu_path_write = menu_path_write
        self.submenu_write = submenu_write
        self.multi_match = multi_match
        self.get_timeout = get_timeout
        self.set_timeout = set_timeout
        self.display_name = display_name
        self.description = description
        if ParameterDictType.has(type) or type == None:
            self.type = type
        else:
            raise InstrumentParameterException("Invalid type specified!")
        self.units = units
        self.value_description = value_description

class ParameterValue(object):
    """
    A parameter's actual value and the information required for updating it
    """
    def __init__(self, name, f_format, value=None, expiration=None):
        self.name = name
        self.value = value
        self.f_format = f_format
        self.expiration = expiration
        self.timestamp = ntplib.system_to_ntp_time(time.time())
                
    def set_value(self, new_val):
        """
        Set the stored value to the new value
        @param new_val The new value to set for the parameter
        """
        self.value = new_val
        self.timestamp = ntplib.system_to_ntp_time(time.time())
    
    def get_value(self, baseline_timestamp=None):
        """
        Get the value from this structure, do whatever checks are necessary
        @param: baseline_timestamp use this time for expiration calculation, default to current time
        @raises InstrumentParameterExpirationException when a parameter is
        too old to work with. Original value is in exception.
        """
        if(baseline_timestamp == None):
            baseline_timestamp = ntplib.system_to_ntp_time(time.time())

        if (self.expiration != None) and  baseline_timestamp > (self.timestamp + self.expiration):
            raise InstrumentParameterExpirationException("Value for %s expired!" % self.name, self.value)
        else:
            return self.value
        
        
class Parameter(object):
    """
    A parameter dictionary item.
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
                 init_value=None,
                 expiration=None,
                 get_timeout=10,
                 set_timeout=10,
                 display_name=None,
                 description=None,
                 type=None,
                 units=None,
                 value_description=None):
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
        self.description = ParameterDescription(name,
                                                menu_path_read=menu_path_read,
                                                submenu_read=submenu_read,
                                                menu_path_write=menu_path_write,
                                                submenu_write=submenu_write,
                                                multi_match=multi_match,
                                                visibility=visibility,
                                                direct_access=direct_access,
                                                startup_param=startup_param,
                                                default_value=default_value,
                                                init_value=init_value,
                                                get_timeout=get_timeout,
                                                set_timeout=set_timeout,
                                                display_name=display_name,
                                                description=description,
                                                type=type,
                                                units=units,
                                                value_description=value_description)
        
        self.value = ParameterValue(name, f_format, value=value,
                                    expiration=expiration)
        self.name = name

    def update(self, input):
        """
        Attempt to udpate a parameter value. By default, this assumes the input
        will be new new value. In subclasses, this must be updated to handle
        a real string of data appropriately.
        @param input A string that is the parameter value.
        @retval True if an update was successful, False otherwise.
        """
        self.value.set_value(input)
        return True
    
    def get_value(self, timestamp=None):
        """
        Get the value of the parameter that has been stored in the ParameterValue
        object.
        @param timestamp timestamp to use for expiration calculation
        @retval The actual data value if it is valid
        @raises InstrumentParameterExpirationException If the value has expired
        """
        return self.value.get_value(timestamp)
    
class RegexParameter(Parameter):
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
                 init_value=None,
                 regex_flags=None,
                 expiration=None,
                 get_timeout=10,
                 set_timeout=10,
                 display_name=None,
                 description=None,
                 type=None,
                 units=None,
                 value_description=None):
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
        @param regex_flags Flags that should be passed to the regex in this
        parameter. Should comply with regex compile() interface (XORed flags).
        @throws TypeError if regex flags are bad
        @see ProtocolParameterDict.add() for details of parameters
        """
        Parameter.__init__(self,
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
                           init_value=init_value,
                           expiration=expiration,
                           get_timeout=get_timeout,
                           set_timeout=set_timeout,
                           display_name=display_name,
                           description=description,
                           type=type,
                           units=units,
                           value_description=value_description)

        self.pattern = pattern
        if regex_flags == None:
            self.regex = re.compile(pattern)
        else:
            self.regex = re.compile(pattern, regex_flags)
            
        self.f_getval = f_getval

    def update(self, input):
        """
        Attempt to update a parameter value. If the input string matches the
        value regex, extract and update the dictionary value.
        @param input A string possibly containing the parameter value.
        @retval True if an update was successful, False otherwise.
        """
        if not (isinstance(input, str)):
            match = self.regex.search(str(input))
        else:
            match = self.regex.search(input)

        if match:
            self.value.set_value(self.f_getval(match))
            return True
        else:
            return False    
    
class FunctionParameter(Parameter):
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
                 init_value=None,
                 expiration=None,
                 get_timeout=10,
                 set_timeout=10,
                 display_name=None,
                 description=None,
                 type=None,
                 units=None,
                 value_description=None):
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
        Parameter.__init__(self,
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
                           init_value=init_value,
                           expiration=expiration,
                           get_timeout=get_timeout,
                           set_timeout=set_timeout,
                           display_name=display_name,
                           description=description,
                           type=type,
                           units=units,
                           value_description=value_description)

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
        orig_value = self.value.get_value()
        result = self.f_getval(input)
        if result != orig_value:
            self.value.set_value(result)
            log.trace('Updated parameter %s=%s', self.name, self.value.get_value())
            return True
        else:
            return False

class ProtocolParameterDict(InstrumentDict):
    """
    Protocol parameter dictionary. Manages, matches and formats device
    parameters.
    """
    def __init__(self):
        """
        Constructor.        
        """
        self._param_dict = {}
        
    def add(self,
            name,
            pattern,
            f_getval,
            f_format,
            value=None,
            visibility=ParameterDictVisibility.READ_WRITE,
            menu_path_read=None,
            submenu_read=None,
            menu_path_write=None,
            submenu_write=None,
            multi_match=False,
            direct_access=False,
            startup_param=False,
            default_value=None,
            init_value=None,
            get_timeout=10,
            set_timeout=10,
            display_name=None,
            description=None,
            type=None,
            units=None,
            regex_flags=None,
            value_description=None,
            expiration=None):
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
        @param get_timeout The number of seconds that should be used as a timeout
        when getting the value from the instrument
        @param set_timeout The number of seconds that should be used as a timeout
        when setting the value to the instrument
        @param display_name The string to use for displaying the parameter
        or a prompt for the parameter value
        @param description The description of what the parameter is
        @param type The type of the parameter (int, float, etc.) Should be a
        ParameterDictType object
        @param regex_flags Flags that should be passed to the regex in this
        parameter. Should comply with regex compile() interface (XORed flags).
        @param units The units of the value (ie "Hz" or "cm")
        @param value_description The description of what values are valid
        for the parameter
        @param expiration The amount of time in seconds before the value
        expires and should not be used. If set to None, the value is always
        valid. If set to 0, the value is never valid from the store.
        """
        val = RegexParameter(name, pattern, f_getval, f_format,
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
                             init_value=init_value,
                             expiration=expiration,
                             get_timeout=get_timeout,
                             set_timeout=set_timeout,
                             display_name=display_name,
                             description=description,
                             type=type,
                             regex_flags=regex_flags,
                             units=units,
                             value_description=value_description)

        self._param_dict[name] = val

    def add_parameter(self, parameter):
        """
        Add a Parameter object to the dictionary or replace an existing one.
        The value can be any object that is an instance of the Parameter class
        or subclasses. This is the preferred method for adding these entries as
        they allow the user to choose the type of parameter to be used
        and make testing more straightforward.
        @param parameter The Parameter object to use
        """
        if not (isinstance(parameter, Parameter)):
            raise InstrumentParameterException(
                "Invalid Parameter added! Attempting to add: %s" % parameter)
        self._param_dict[parameter.name] = parameter
        
    def get(self, name, timestamp=None):
        """
        Get a parameter value from the dictionary.
        @param name Name of the value to be retrieved.
        @param timestamp Timestamp to use for expiration calculation
        @raises KeyError if the name is invalid.
        """
        return self._param_dict[name].get_value(timestamp)

    def get_current_timestamp(self, offset=0):
        """
        Get the current time in a format suitable for parameter expiration calculation.
        @param offset: seconds from the current time to offset the timestamp
        @return: a unix timestamp
        """
        return ntplib.system_to_ntp_time(time.time()) + offset

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
        @raises InstrumentParameterException if the description is missing
        """
        if not self._param_dict[name].description:
            raise InstrumentParameterException("No description present!")
            
        return self._param_dict[name].description.init_value            

    def get_default_value(self, name):
        """
        Get a parameter's default value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        @raises InstrumentParameterException if the description is missing        
        """
        if not self._param_dict[name].description:
            raise InstrumentParameterException("No description present!")

        return self._param_dict[name].description.default_value
    
    def set_value(self, name, value):
        """
        Set a parameter's value in the dictionary. While this is a simple,
        straight forward way of setting things, the update routine might be
        a more graceful (and possibly more robust) way to automatically
        handling strings directly from an instrument. Consider using update()
        wherever it makes sense.
        
        @param name The parameter name.
        @param value The parameter object to insert (and possibly overwrite)
        into the parameter dictionary.
        @raises KeyError if the name is invalid.
        @see ProtocolParameterDict.update()
        """        
        log.debug("Setting parameter dict name: %s to value: %s", name, value)
        self._param_dict[name].value.set_value(value)
    
    def set_default(self, name):
        """
        Set the value to the default value stored in the param dict
        @raise KeyError if the name is invalid
        @raise ValueError if the default_value is missing
        @raises InstrumentParameterException if the description is missing        
        """
        if not self._param_dict[name].description:
            raise InstrumentParameterException("No description present!")

        if self._param_dict[name].description.default_value is not None:
            self._param_dict[name].value.set_value(self._param_dict[name].description.default_value)
        else:
            raise ValueError("Missing default value")
            
    def set_init_value(self, name, value):
        """
        Set the value to the default value stored in the param dict
        @param The parameter name to add to
        @param The value to set for the initialization variable
        @raise KeyError if the name is invalid
        @raises InstrumentParameterException if the description is missing        
        """
        if not self._param_dict[name].description:
            raise InstrumentParameterException("No description present!")

        self._param_dict[name].description.init_value = value
        
    def get_menu_path_read(self, name):
        """
        Get the read menu path parameter value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        @raises InstrumentParameterException if the description is missing        
        """
        if not self._param_dict[name].description:
            raise InstrumentParameterException("No description present!")

        return self._param_dict[name].description.menu_path_read
        
    def get_submenu_read(self, name):
        """
        Get the read final destination submenu parameter value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        @raises InstrumentParameterException if the description is missing                
        """
        if not self._param_dict[name].description:
            raise InstrumentParameterException("No description present!")

        return self._param_dict[name].description.submenu_read
        
    def get_menu_path_write(self, name):
        """
        Get the write menu path parameter value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        @raises InstrumentParameterException if the description is missing                
        """
        if not self._param_dict[name].description:
            raise InstrumentParameterException("No description present!")

        return self._param_dict[name].description.menu_path_write
        
    def get_submenu_write(self, name):
        """
        Get the write final destination parameter value from the dictionary.
        @param name Name of the value to be retrieved.
        @raises KeyError if the name is invalid.
        @raises InstrumentParameterException if the description is missing                
        """
        if not self._param_dict[name].description:
            raise InstrumentParameterException("No description present!")

        return self._param_dict[name].description.submenu_write

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
            if multi_mode == True and val.description.multi_match == False:
                continue
            if val.update(input):
                hit_count =hit_count +1
                if False == val.description.multi_match:
                    return hit_count
                else:
                    multi_mode = True

        if False == multi_mode and input <> "":
            log.debug("protocol_param_dict.py UNMATCHCHED ***************************** %s", input)
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

    def update(self, input, target_params=None):
        """
        Update the dictionaray with a line input. Iterate through all objects
        and attempt to match and update a parameter. Only updates the first
        match encountered. If we pass in a target params list then will will
        only iterate through those allowing us to limit upstate to only specific
        parameters.
        @param input A string to match to a dictionary object.
        @param target_params a name, or list of names to limit the scope of
        the update.
        @retval The name that was successfully updated, None if not updated
        @raise InstrumentParameterException on invalid target prams
        @raise KeyError on invalid parameter name
        """
        log.debug("update input: %s", input)
        found = False

        if(target_params and isinstance(target_params, str)):
            params = [target_params]
        elif(target_params and isinstance(target_params, list)):
            params = target_params
        elif(target_params == None):
            params = self._param_dict.keys()
        else:
            raise InstrumentParameterException("invalid target_params, must be name or list")

        for name in params:
            log.trace("update param dict name: %s", name)
            val = self._param_dict[name]
            if val.update(input):
                found = True
        return found

    def get_all(self, timestamp=None):
        """
        Retrive the configuration (all settable key values).
        @param timestamp baseline timestamp to use for expiration
        @retval name : value configuration dict.
        """
        config = {}
        for (key, val) in self._param_dict.iteritems():
            config[key] = val.get_value(timestamp)
        return config

    def get_config(self):
        """
        Retrive the configuration (all settable key values).
        @retval name : value configuration dict.
        """
        config = {}
        for (key, val) in self._param_dict.iteritems():
            if(self.is_settable_param(key)):
               config[key] = val.get_value()
        return config

    def format(self, name, val=None):
        """
        Format a parameter for a set command.
        @param name The name of the parameter.
        @param val The parameter value.
        @retval The value formatted as a string for writing to the device.
        @raises InstrumentProtocolException if the value could not be formatted
        or value object is missing.
        @raises KeyError if the parameter name is invalid.
        """
        if not self._param_dict[name].value:
            raise InstrumentParameterException("No value present for %s!" % name)

        if val == None:
            current_value = self._param_dict[name].value.get_value()
        else:
            current_value = val
        
        return self._param_dict[name].value.f_format(current_value)
        
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
        @raises InstrumentParameterException if the description is missing                
        """

        return_val = []
        for key in self._param_dict.keys():

            if not self._param_dict[key].description:
                raise InstrumentParameterException("No description present!")

            if self._param_dict[key].description.direct_access == True:
                return_val.append(key)
        
        return return_val

    def is_settable_param(self, name):
        """
        Return true if a parameter is not read only
        @param name name of a parameter
        @retval True if the parameter is flagged as not read only
        @raises KeyError if parameter doesn't exist
        @raises InstrumentParameterException if the description is missing
        """
        if not self._param_dict[name].description:
            raise InstrumentParameterException("No description present!")

        return not (self._param_dict[name].description.visibility == ParameterDictVisibility.READ_ONLY)

    def is_startup_param(self, name):
        """
        Return true if a parameter name references a startup parameter
        @param name name of a parameter
        @retval True if the parameter is flagged as a startup param
        @raises KeyError if parameter doesn't exist
        @raises InstrumentParameterException if the description is missing                
        """
        if not self._param_dict[name].description:
            raise InstrumentParameterException("No description present!")

        return self._param_dict[name].description.startup_param == True

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
            if self._param_dict[key].description.visibility == visibility:
                return_val.append(key)
        
        return return_val
    
    def generate_dict(self):
        """
        Generate a JSONifyable metadata schema that describes the parameters.
        This could be passed up toward the agent for ultimate handing to the UI.
        This method only handles the parameter block of the schema.
        """
        return_struct = {}
        
        for param_key in self._param_dict.keys():
            param_struct = {}
            value_struct = {}
            if self._param_dict[param_key] != None:
                param_obj = self._param_dict[param_key].description
            # Description objects
            if param_obj.get_timeout != None:
                param_struct[ParameterDictKey.GET_TIMEOUT] = param_obj.get_timeout
            if param_obj.set_timeout != None:
                param_struct[ParameterDictKey.SET_TIMEOUT] = param_obj.set_timeout
            if param_obj.visibility != None:
                param_struct[ParameterDictKey.VISIBILITY] = param_obj.visibility
            if param_obj.startup_param != None:
                param_struct[ParameterDictKey.STARTUP] = param_obj.startup_param
            if param_obj.direct_access != None:
                param_struct[ParameterDictKey.DIRECT_ACCESS] = param_obj.direct_access
            if param_obj.display_name != None:
                param_struct[ParameterDictKey.DISPLAY_NAME] = param_obj.display_name
            if param_obj.description != None:
                param_struct[ParameterDictKey.DESCRIPTION] = param_obj.description
            
            # Value objects
            if param_obj.type != None:
                value_struct[ParameterDictKey.TYPE] = param_obj.type
            if param_obj.default_value != None:
                value_struct[ParameterDictKey.DEFAULT] = param_obj.default_value
            if param_obj.units != None:
                value_struct[ParameterDictKey.UNITS] = param_obj.units
            if param_obj.description != None:
                value_struct[ParameterDictKey.DESCRIPTION] = param_obj.value_description
            
            param_struct[ParameterDictKey.VALUE] = value_struct            
            return_struct[param_key] = param_struct
        
        return return_struct
    
    def load_strings(self, devel_path=None, filename=None):
        """
        Load the metadata for a parameter set. starting by looking at the default
        path in the egg and filesystem first, overriding what might have been
        hard coded. If a system filename is given look there. If parameter
        strings cannot be found, return False and carry on with hard coded values.
        
        @param devel_path The path where the file can be found during development.
        This is likely in the mi/instrument/make/model/flavor/resource directory.    
        @param filename The filename of the custom file to load, including as full a path
        as desired (complete path recommended)
        @retval True if something could be loaded, False otherwise
        """
        log.debug("Loading parameter dictionary strings, dev path is %s, filename is %s",
                  devel_path, filename)
        # if the file is in the default spot of the working path or egg, get that one
        try:
            metadata = self.get_metadata_from_source(devel_path, filename)
        except IOError as e:
            log.warning("Encountered IOError: %s", e)
            return False        # Fill the fields           

        if metadata:
            log.debug("Found parameter metadata, loading dictionary")
            for (param_name, param_value) in metadata[ParameterDictKey.PARAMETERS].items():
                log.trace("load_strings setting param name/value: %s / %s", param_name, param_value)
                for (name, value) in param_value.items():
                    if param_name not in self._param_dict:
                        continue
                    if (name == ParameterDictKey.DESCRIPTION):
                        self._param_dict[param_name].description.description = value
                    if name == ParameterDictKey.DISPLAY_NAME:
                        self._param_dict[param_name].description.display_name = value
                    if name == ParameterDictKey.UNITS:
                        self._param_dict[param_name].description.units = value
                    if name == ParameterDictKey.TYPE:
                        self._param_dict[param_name].description.type = value
                    if name == ParameterDictKey.VALUE_DESCRIPTION:
                        self._param_dict[param_name].description.value_description = value
            return True
    
        return False # no metadata!
        
