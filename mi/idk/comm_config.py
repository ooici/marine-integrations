"""
@file coi-services/mi.idk/comm_config.py
@author Bill French
@brief Comm Configuration object used to gather and store connection information for the logger.

Usage:

#
# Create a CommConfig object.  Use the factory method to get the correct object type.
#
comm_config = get_config_from_type(filename, 'ethernet'):

#
# Get config from the console (prompts for type)
#
comm_config = comm_config.get_from_console(filename)

#
# List all know CommConfig types
#
valid_types = CommConfig.valid_type_list()

"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import sys
import os

import yaml

from mi.idk import prompt
from mi.idk.config import Config
from mi.core.log import get_logger ; log = get_logger()

from mi.idk.exceptions import DriverParameterUndefined
from mi.idk.exceptions import NoConfigFileSpecified
from mi.idk.exceptions import CommConfigReadFail
from mi.idk.exceptions import InvalidCommType

DEFAULT_DATA_PORT = 5000
DEFAULT_CMD_PORT = 5001

class CommConfig(object):
    """
    Object to collect and store logger configuration information
    """
    def __init__(self, config_file_path = None):
        """
        @brief Constructor, attempt to read from a config file 
        @param metadata IDK Metadata object
        """
        self.config_file_path = None
        self.data_port = None
        self.command_port = None
        if config_file_path:
            self.read_from_file(config_file_path)

    def __getitem__(self, *args):
        return args;
        
    def _init_from_yaml(self, yamlInput):
        """
        @brief initialize the object from yaml data.  This method should be sub classed
        @param yamlInput yaml data structure
        """
        if( yamlInput ):
            self.config_type = yamlInput['comm'].get('method')

            self.data_port = yamlInput['comm'].get('data_port')
            self.command_port = yamlInput['comm'].get('command_port')

            if(self.data_port): self.data_port = int(self.data_port)
            if(self.command_port): self.command_port = int(self.command_port)

    def _config_dictionary(self):
        """
        @brief get a dictionary of configuration parameters.  This method should be sub classed to extend config
        @retval dictionary containing all config parameters.
        """
        
        if(self.data_port): self.data_port = int(self.data_port)
        if(self.command_port): self.command_port = int(self.command_port)

        return { 'method': self.method(),
                 'data_port': self.data_port,
                 'command_port': self.command_port }


    ###
    #   Public Methods
    ###
    def display_config(self):
        """
        @brief Pretty print object configuration to stdout.  This method should be sub classed.
        """
        print( "Type: " + self.method() )
        print( "PA Command Port: " + str(self.command_port) )
        print( "PA Data Port: " + str(self.data_port) )


    def serialize(self):
        """
        @brief Get yaml dump of object data
        @retval yaml string of object data
        """
        return yaml.dump( {'comm': self._config_dictionary()
        }, default_flow_style=False)

    def dict(self):
        """
        @brief Return a dict for the comm config
        @retval dict of all comm config data
        """
        return self._config_dictionary()
        
    def store_to_file(self):
        """
        @brief Store object config data to a config file.
        """
        if not self.config_file_path:
            raise NoConfigFileSpecified()
                
        log.info("store config to %s" % self.config_file_path)
                
        ofile = open( self.config_file_path, 'w' )

        ofile.write( self.serialize() )
        ofile.close()

    def read_from_file(self,filename):
        """
        @brief Read config file and initialize this object
        @param filename filename that contains the config
        """
        self.config_file_path = filename

        log.debug("read comm config file %s", filename)
        # If the config file doesn't exists don't read
        if self.config_file_path and os.path.exists(self.config_file_path):
            try:
                infile = open( filename, "r" )
                input = yaml.load( infile )
    
                if( input ):
                    self._init_from_yaml( input )
    
                infile.close()
            except IOError:
                raise CommConfigReadFail(msg="filename: %s" % filename)
            

    def get_from_console(self):
        """
        @brief Read comm config from the console.  This should be overloaded in a sub class.
        """
        if(not self.data_port): self.data_port = DEFAULT_DATA_PORT
        if(not self.command_port): self.command_port = DEFAULT_CMD_PORT

        self.data_port = prompt.text( 'Port Agent Data Port', self.data_port )
        self.command_port = prompt.text( 'Port Agent Command Port', self.command_port )

        if( self.confirm_config() ):
            self.store_to_file()
        else:
            return self.get_from_console()

    def confirm_config(self):
        """
        @brief Is the data entered on the console valid?  This should be overloaded in the sub class to do something useful.
        """
        return True


    ###
    #   Static Methods
    ###
    @staticmethod
    def config_filename():
        """
        @brief name of the file that stores the comm configuration yaml
        """
        return "comm_config.yml"
    
    @staticmethod
    def method():
        """
        @brief Defines the "type" of object.  This must be overloaded in the sub class.
        @retval type of comm configuration object.
        """
        return False

    @staticmethod
    def get_config_from_console(filename, default_type = None):
        """
        @brief Factory method.  Prompt and read the config type from the console
        @param filename The file where the comm config is stored in
        @retval A CommConfig object for the type entered on the console
        """
        print( "\nDriver Comm Configuration" )

        # Currently there is only one connection type so let's just default to that
        #type = prompt.text( 'Type [' + CommConfig.valid_type_string() + ']', default_type )
        type='ethernet'
        print "Type: ethernet"

        config = CommConfig.get_config_from_type(filename, type)

        if( config ):
            return config
        else:
            return CommConfig.get_config_from_console(filename, default_type)

    @staticmethod
    def get_config_from_type(filename, type):
        """
        @brief Factory method.  Get a CommConfig object for the type passed in
        @param filename The file where the comm config is stored in
        @param type Type of CommConfig object to create
        @retval A CommConfig object for the type entered on the console
        """
        valid_types = CommConfig.valid_type_list()
        if( valid_types.count( type ) ):
            config = CommConfigEthernet(filename)
            return config
        else:
            raise InvalidCommType(msg=type)

    @staticmethod
    def get_config_from_file(filename):
        """
        @brief Factory method.  Get a CommConfig object for the type stored in a driver comm_config file
        @param filename The file where the comm config is stored in
        @retval A CommConfig object for the type specified in the comm config file.
        """
        config = CommConfig(filename)

        return CommConfig.get_config_from_type(filename,config.config_type)

    @staticmethod
    def valid_type_list():
        """
        @brief List all know types of CommConfig objects
        @retval list of all know CommConfig objects
        """
        result = []
        for config in _CONFIG_OBJECTS:
            result.append(config.method())
        return result

    @staticmethod
    def valid_type_string():
        """
        @brief Get a pretty print list of valid CommConfig object types
        @retval comma delimited string of valid CommConfig object types
        """
        return ", ".join(CommConfig.valid_type_list())


class CommConfigEthernet(CommConfig):
    """
    Ethernet CommConfig object.  Defines data store for ethernet based loggers connections
    """

    @staticmethod
    def method(): return 'ethernet'

    def __init__(self, filename):
        self.device_addr = None
        self.device_port = None

        CommConfig.__init__(self, filename)

    def _init_from_yaml(self, yamlInput):
        CommConfig._init_from_yaml(self, yamlInput)

        if( yamlInput ):
            self.device_addr = yamlInput['comm'].get('device_addr')
            self.device_port = yamlInput['comm'].get('device_port')

    def get_from_console(self):
        self.device_addr = prompt.text( 'Device Address', self.device_addr )
        self.device_port = prompt.text( 'Device Port', self.device_port )
        CommConfig.get_from_console(self)

    def display_config(self):
        CommConfig.display_config(self)
        print( "Device Address: " + self.device_addr )
        print( "Device Port: " + str(self.device_port ))

    def _config_dictionary(self):
        config = CommConfig._config_dictionary(self)
        config['device_addr'] = self.device_addr
        config['device_port'] = int(self.device_port)

        return config


# List of all known CommConfig objects
_CONFIG_OBJECTS = [ CommConfigEthernet ]


if __name__ == '__main__':
    pass

