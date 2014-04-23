#!/user/bin/env python

"""
@package mi.dataset.param_dict
@file mi/dataset/param_dict.py
@author Emily Hahn
@brief Extend the protocol param dict to handle dataset encoding exceptions
"""
import re

from mi.core.instrument.protocol_param_dict import ProtocolParameterDict, ParameterDescription
from mi.core.instrument.protocol_param_dict import ParameterValue, ParameterDictVisibility

from mi.core.log import get_logger ; log = get_logger()

class DatasetParameterValue(ParameterValue):
    def clear_value(self):
        """
        Ensure value is cleared to None
        """
        self.value = None

class Parameter(object):
    """
    A parameter dictionary item.
    """
    def __init__(self, name, f_format, value=None, expiration=None):
        """
        Parameter value constructor.
        @param name The parameter name.
        @param f_format The function that formats the parameter value for a set command.
        @param value The parameter value (initializes to None).
        """
        self.description = ParameterDescription(name,
                                                menu_path_read=None,
                                                submenu_read=None,
                                                menu_path_write=None,
                                                submenu_write=None,
                                                multi_match=False,
                                                visibility=ParameterDictVisibility.READ_WRITE,
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
                                                value_description=None)
        
        self.value = DatasetParameterValue(name, f_format, value=value,
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

    def clear_value(self):
        """
        Clear the value in the parameter by setting it to None
        """
        self.value.clear_value()

class RegexParameter(Parameter):
    def __init__(self, name, pattern, f_getval, f_format, value=None,
                 regex_flags=None, expiration=None):
        """
        Parameter value constructor.
        @param name The parameter name.
        @param pattern The regex that matches the parameter in line output.
        @param f_getval The fuction that extracts the value from a regex match.
        @param f_format The function that formats the parameter value for a set command.
        @param value The parameter value (initializes to None).
        @param regex_flags Flags that should be passed to the regex in this
        parameter. Should comply with regex compile() interface (XORed flags).
        @throws TypeError if regex flags are bad
        @see ProtocolParameterDict.add() for details of parameters
        """
        Parameter.__init__(self, name, f_format, value=value, expiration=expiration)

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

class DatasetParameterDict(ProtocolParameterDict):
    """
    Dataset parameter dictionary. Manages, matches and formats parameters.
    """
    def __init__(self):
        """
        Constructor.        
        """
        super(DatasetParameterDict, self).__init__()
        self._encoding_errors = []

    def add(self, name, pattern, f_getval, f_format, value=None, regex_flags=None):
        """
        Add a parameter object to the dictionary using a regex for extraction.
        @param name The parameter name.
        @param pattern The regex that matches the parameter in line output.
        @param f_getval The fuction that extracts the value from a regex match.
        @param f_format The function that formats the parameter value for a set command.
        @param regex_flags Flags that should be passed to the regex in this
        parameter. Should comply with regex compile() interface (XORed flags).
        """
        val = RegexParameter(name, pattern, f_getval, f_format, value=value, regex_flags=regex_flags)
        self._param_dict[name] = val

    def update(self, in_data):
        """
        Update the dictionaray with a line input. Iterate through all objects
        and attempt to match and update a parameter. Only updates the first
        match encountered. If we pass in a target params list then will will
        only iterate through those allowing us to limit upstate to only specific
        parameters.
        @param in_data A set of data to match to a dictionary object.
        @raise InstrumentParameterException on invalid target prams
        @raise KeyError on invalid parameter name
        """
        params = self._param_dict.keys()

        for name in params:
            log.trace("update param dict name: %s", name)
            try:
                val = self._param_dict[name]
                val.update(in_data)
            except Exception as e:
                # set the value to None if we failed
                val.clear_value()
                log.error("Dataset parameter dict error encoding Name:%s, set to None", name)
                self._encoding_errors.append({name: None})

    def get_encoding_errors(self):
        """
        Return the encoding errors list
        """
        return self._encoding_errors
