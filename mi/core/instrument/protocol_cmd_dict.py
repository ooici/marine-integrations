#!/usr/bin/env python

"""
@package ion.services.mi.protocol_cmd_dict
@file ion/services/mi/protocol_cmd_dict.py
@author Steve Foley
@brief A dictionary class that manages metadata about the commands supported
by the driver
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import json
from mi.core.common import BaseEnum
from mi.core.exceptions import InstrumentParameterException

from mi.core.log import get_logger ; log = get_logger()

class CommandDictType(BaseEnum):
    INT = "int"
    STRING = "string"
    FLOAT = "float"
    LIST = "list"
    BOOLEAN = "bool"

class CommandDictKeys(BaseEnum):
    DISPLAY_NAME = "display_name"
    DESCRIPTION = "description"
    TIMEOUT = "timeout"
    VALUE = "value"
    TYPE = "type"
    REQUIRED = "required"
    UNITS = "units"
    ARGUMENTS = "arguments"
    COMMANDS = "commands"
    RETURN = "return"
        
class CommandArgument(object):
    """
    An object handling the description of the generally static description of
    one of the command's arguments
    """
    def __init__(self,
                 name,
                 required=False,
                 display_name=None,
                 description=None,
                 type=None,
                 units=None,
                 value_description=None):
        """
        Create a command argument structure
        @param name The command name.
        @param required A boolean indicating that the argument is required
        @param display_name The string to use for displaying the command
        or a prompt for the command use
        @param description The description of what the command is
        @param type The type of the argument (int, float, etc.). Should be a
        CommandDictType object
        @param units The units of the argument (ie "Hz" or "cm")
        @param description The description of the argument
        @param value_description A description of what values are allowed for
        this argument (ie. "An integer in the range 1-20")
        @raises InstrumentParameterException If non-list or non-CommandArgument objects are
        fed in as arguments.
        """
        self.name = name
        self.required = required
        self.type = type
        self.units = units
        self.display_name = display_name
        self.description = description
        self.value_description = value_description
    
    def generate_dict(self):
        """
        Create a dict object for this argument that can be JSONified. The
        output is intended to be included with the larger command's structure
        before being turned into a JSON string
        @retval A dict that can be ultiamtely parsed into JSON
        """
        value_dict = {}
        return_dict = {}
        
        # description array
        #if self.name != None:
        #    return_dict[CommandDictKeys.NAME] = self.name
        if self.required != None:
            return_dict[CommandDictKeys.REQUIRED] = self.required
        if self.display_name != None:
            return_dict[CommandDictKeys.DISPLAY_NAME] = self.display_name
        if self.description != None:
            return_dict[CommandDictKeys.DESCRIPTION] = self.description
        
        # value array
        if self.units != None:
            value_dict[CommandDictKeys.UNITS] = self.units
        if self.type != None:
            value_dict[CommandDictKeys.TYPE] = self.type
        if self.value_description != None:
            value_dict[CommandDictKeys.DESCRIPTION] = self.value_description
        
        return_dict[CommandDictKeys.VALUE] = value_dict
        return return_dict
        
class Command(object):
    """
    An object handling the descriptive (and largely staticly defined in code)
    qualities of a parameter.
    """
    def __init__(self,
                 name,
                 timeout=10,
                 display_name=None,
                 description=None,
                 return_type=None,
                 return_units=None,
                 return_description=None,
                 arguments=[]):
                
        """
        Create a Command
        @param name The command name.
        @param timeout The timeout associated with the entire command operation
        @param display_name The string to use for displaying the command
        or a prompt for the command use
        @param description The description of what the command is
        @param return_type The type of the command's return value (int,
        float, etc.). Should be a CommandDictType object
        @param return_units The units of the command's return value (ie "Hz"
        or "cm")
        @param return_description The description of the command's return value
        @param arguments A list of CommandArgument structures that describe the
        command that is being added
        @raises InstrumentParameterException If non-list or non-CommandArgument objects are
        fed in as arguments.
        """
        self.name = name
        self.timeout = timeout
        self.display_name = display_name
        self.description = description
        self.return_type = return_type
        self.return_units = return_units
        self.return_description = return_description

        if not isinstance(arguments, list):
            raise InstrumentParameterException("Invalid argument list format!")
            
        for arg in arguments:
            if not isinstance(arg, CommandArgument):
                raise InstrumentParameterException("Argument for command %s, argument %s not valid format"
                                                   % (name, arg))

        self.arguments = arguments
        
    def generate_dict(self):
        """
        Generate the dictionary structure that describes the complete command.
        It should be able to generate JSON as the intent is to include this in
        the grand schema of the command dictionary before JSON is generated.
        
        @retval A JSON-izable Python dict that describes the command, its return
        values, and its arguments
        """
        args_dict = {}
        retval_dict = {}
        return_dict = {}
        
        if self.timeout != None:
            return_dict[CommandDictKeys.TIMEOUT] = self.timeout
        if self.display_name != None:
            return_dict[CommandDictKeys.DISPLAY_NAME] = self.display_name
        if self.description != None:
            return_dict[CommandDictKeys.DESCRIPTION] = self.description

        # fill in return value info
        if self.return_type != None:
            retval_dict[CommandDictKeys.TYPE] = self.return_type
        if self.return_units != None:
            retval_dict[CommandDictKeys.UNITS] = self.return_units
        if self.return_description != None:
            retval_dict[CommandDictKeys.DESCRIPTION] = self.return_description
        
        # fill in the arguments
        for arg in self.arguments:
            args_dict[arg.name] = arg.generate_dict()        
        
        return_dict[CommandDictKeys.ARGUMENTS] = args_dict
        return_dict[CommandDictKeys.RETURN] = retval_dict
        
        return return_dict
    
class ProtocolCommandDict(object):
    """
    Protocol parameter dictionary. Manages, matches and formats device
    parameters.
    """
    def __init__(self):
        """
        Constructor.        
        """
        self._cmd_dict = {}
        
    def add(self,
            name,
            timeout=10,
            display_name=None,
            description=None,
            return_type=None,
            return_units=None,
            return_description=None,
            arguments=[]):
        """
        Add a Command object to the dictionary.
        @param name The command name.
        @param timeout The timeout associated with the entire command operation
        @param display_name The string to use for displaying the command
        or a prompt for the command use
        @param description The description of what the command is
        @param return_type The type of the command's return value (int,
        float, etc.). Should be a CommandDictType object
        @param return_units The units of the command's return value (ie "Hz"
        or "cm")
        @param return_description The description of the command's return value
        @param arguments A list of CommandArgument structures that describe the
        command that is being added
        """      
        val = Command(name,
                      timeout=timeout,
                      display_name=display_name,
                      description=description,
                      return_type=return_type,
                      return_units=return_units,
                      return_description=return_description,
                      arguments=arguments)

        self._cmd_dict[name] = val

    def add_command(self, command):
        """
        Add or overwrite a command to the list
        @param command A Command item to be added to the list
        """
        if not isinstance(command, Command):
            raise InstrumentParameterException("Invalid command structure!")

        if not isinstance(command.name, str):
            raise InstrumentParameterException("Invalid command structure!")

        self._cmd_dict[command.name] = command
        
    def get_command(self, name):
        """
        Get the command by name.
        @param name The name of the command to retreive
        @retval The Command object that represents the specified command,
        None if no command exists.
        """
        if name == None:
            return None
        
        if name not in self._cmd_dict.keys():
            return None
        
        return self._cmd_dict[name]
        
    def generate_schema(self):
        """
        Generate a JSON metadata schema that describes the parameters. This could
        be passed up toward the agent for ultimate handing to the UI.
        This method only handles the parameter block of the schema.
        """
        return_struct = {}
        
        for cmd in self._cmd_dict.keys():
            return_struct[cmd] = self._cmd_dict[cmd].generate_dict()
        
        return json.dumps(return_struct, indent=4, sort_keys=True)
            
        
        