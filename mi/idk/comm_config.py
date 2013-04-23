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
from mi.core.common import BaseEnum

DEFAULT_HOST = 'localhost'
DEFAULT_DATA_PORT = 6001
DEFAULT_CMD_PORT = 6002
DEFAULT_SNIFFER_PORT = 6003

class ConfigTypes(BaseEnum):
    ETHERNET = 'ethernet'
    SERIAL = 'serial'
    BOTPT = 'botpt'

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
        self.host = DEFAULT_HOST
        self.sniffer_port = DEFAULT_SNIFFER_PORT
        self.sniffer_prefix = None
        self.sniffer_suffix = None

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

            self.host = yamlInput['comm'].get('host')
            self.data_port = yamlInput['comm'].get('data_port')
            self.command_port = yamlInput['comm'].get('command_port')

            self.sniffer_port = yamlInput['comm'].get('sniffer_port')
            self.sniffer_prefix = yamlInput['comm'].get('sniffer_prefix')
            self.sniffer_suffix = yamlInput['comm'].get('sniffer_suffix')

            if(self.data_port): self.data_port = int(self.data_port)
            if(self.command_port): self.command_port = int(self.command_port)

    def _config_dictionary(self):
        """
        @brief get a dictionary of configuration parameters.  This method should be sub classed to extend config
        @retval dictionary containing all config parameters.
        """
        
        if(self.data_port): self.data_port = int(self.data_port)
        if(self.command_port): self.command_port = int(self.command_port)
        if(self.sniffer_port): self.sniffer_port = int(self.sniffer_port)

        result = { 'method': self.method(),
                 'data_port': self.data_port,
                 'command_port': self.command_port,
                 'host': self.host,
                 'sniffer_port': self.sniffer_port,
        }

        if(self.sniffer_prefix): result['sniffer_prefix'] = self.sniffer_prefix
        if(self.sniffer_suffix): result['sniffer_suffix'] = self.sniffer_suffix

        return result

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
        if(not self.host): self.host = DEFAULT_HOST
        if(not self.data_port): self.data_port = DEFAULT_DATA_PORT
        if(not self.command_port): self.command_port = DEFAULT_CMD_PORT
        if(not self.sniffer_port): self.sniffer_port = DEFAULT_SNIFFER_PORT

        self.host = prompt.text( 'Port Agent Host', self.host )
        self.data_port = prompt.text( 'Port Agent Data Port', self.data_port )
        self.command_port = prompt.text( 'Port Agent Command Port', self.command_port )
        self.sniffer_port = prompt.text( 'Port Agent Sniffer Port', self.sniffer_port )
        #self.sniffer_prefix = prompt.text( 'Port Agent Sniffer Prefix', self.sniffer_prefix )
        #self.sniffer_suffix = prompt.text( 'Port Agent Sniffer Suffix', self.sniffer_suffix )

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
    def get_config_from_console(filename, default_type = ConfigTypes.ETHERNET):
        """
        @brief Factory method.  Prompt and read the config type from the console
        @param filename The file where the comm config is stored in
        @retval A CommConfig object for the type entered on the console
        """
        print( "\nDriver Comm Configuration" )

        # Currently there is only one connection type so let's just default to that

        type = prompt.text( 'Type [' + CommConfig.valid_type_string() + ']', default_type )
        #type=ConfigTypes.ETHERNET
        #print "Type: ethernet"

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
        if( type in valid_types ):
            if ConfigTypes.ETHERNET == type:
                config = CommConfigEthernet(filename)
            elif ConfigTypes.BOTPT == type:
                config = CommConfigBOTPT(filename)
            elif ConfigTypes.SERIAL == type:
                config = CommConfigSerial(filename)
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
    def method(): return ConfigTypes.ETHERNET

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


class CommConfigBOTPT(CommConfig):
    """
    BOTPT CommConfig object.  Defines data store for botpt connections
    """

    @staticmethod
    def method(): return ConfigTypes.BOTPT

    def __init__(self, filename):
        self.device_addr = None
        self.device_tx_port = None
        self.device_rx_port = None

        CommConfig.__init__(self, filename)

    def _init_from_yaml(self, yamlInput):
        CommConfig._init_from_yaml(self, yamlInput)

        if( yamlInput ):
            self.device_addr = yamlInput['comm'].get('device_addr')
            self.device_tx_port = yamlInput['comm'].get('device_tx_port')
            self.device_rx_port = yamlInput['comm'].get('device_rx_port')

    def get_from_console(self):
        self.device_addr = prompt.text( 'Device Address', self.device_addr )
        self.device_tx_port = prompt.text( 'Device TX Port', self.device_tx_port )
        self.device_rx_port = prompt.text( 'Device RX Port', self.device_rx_port )
        CommConfig.get_from_console(self)

    def display_config(self):
        CommConfig.display_config(self)
        print( "Device Address: " + self.device_addr )
        print( "Device TX Port: " + str(self.device_tx_port ))
        print( "Device RX Port: " + str(self.device_rx_port ))

    def _config_dictionary(self):
        config = CommConfig._config_dictionary(self)
        config['device_addr'] = self.device_addr
        config['device_tx_port'] = int(self.device_tx_port)
        config['device_rx_port'] = int(self.device_rx_port)

        return config


class CommConfigSerial(CommConfig):
    """
    Serial CommConfig object.  Defines data store for serial based loggers connections
    """

    @staticmethod
    def method(): return ConfigTypes.SERIAL

    def __init__(self, filename):
        self.device_os_port = None
        self.device_baud = None
        self.device_data_bits = None
        self.device_parity = None
        self.device_stop_bits = None
        self.device_flow_control = None # hardware/software/none

        CommConfig.__init__(self, filename)

    def _init_from_yaml(self, yamlInput):
        CommConfig._init_from_yaml(self, yamlInput)

        if( yamlInput ):
            self.device_os_port = yamlInput['comm'].get('device_os_port')
            self.device_baud = yamlInput['comm'].get('device_baud')
            self.device_data_bits = yamlInput['comm'].get('device_data_bits')
            self.device_parity = yamlInput['comm'].get('device_parity')
            self.device_stop_bits = yamlInput['comm'].get('device_stop_bits')
            self.device_flow_control = yamlInput['comm'].get('device_flow_control')

    def get_from_console(self):
        self.device_os_port = prompt.text( 'Device OS Port', self.device_os_port )
        self.device_baud = prompt.text( 'Device Baud', self.device_baud )
        if int(self.device_baud) not in [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]:
            raise InvalidCommType(str(self.device_baud) + " is not an allowed value for device baud. " +\
                                  "[1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]")
        self.device_data_bits = prompt.text( 'Device Data Bits', self.device_data_bits )
        if int(self.device_data_bits) not in [5, 6, 7, 8]:
            raise InvalidCommType(str(self.device_data_bits) +\
                                  " is not an allowed value for device data bits [5, 6, 7, 8].")
        self.device_parity = prompt.text( 'Device Parity', self.device_parity )
        if 'n' == self.device_parity.lower() or 'none' == self.device_parity.lower():
            self.device_parity = 0
        elif 'o' == self.device_parity.lower() or 'odd' == self.device_parity.lower():
            self.device_parity = 1
        elif 'e' == self.device_parity.lower() or 'even' == self.device_parity.lower():
            self.device_parity = 2
        elif 0 <= self.device_parity <= 2:
            """
            acceptable
            """
        else:
            raise InvalidCommType(str(self.device_parity) + \
                                  " is not an allowed value for device parity. [none, odd, even]")
        self.device_stop_bits = prompt.text( 'Device Stop Bits', self.device_stop_bits )
        if int(self.device_stop_bits) not in [0, 1, 2]:
            raise InvalidCommType(str(self.device_stop_bits) + \
                                  " is not an allowed value for device stop bits [0, 1, 2].")
        self.device_flow_control = prompt.text( 'Device Flow Control', self.device_flow_control )

        if 'n' == self.device_flow_control.lower() or 'none' == self.device_flow_control.lower():
            self.device_flow_control = 0
        elif 'h' == self.device_flow_control.lower() or 'hardware' == self.device_flow_control.lower():
            self.device_flow_control = 1
        elif 's' == self.device_flow_control.lower() or 'software' == self.device_flow_control.lower():
            self.device_flow_control = 2
        elif 0 <= self.device_flow_control <= 2:
            """
            acceptable
            """
        else:
            raise InvalidCommType(str(self.device_flow_control) + \
                                  " is not an allowed value for device flow control. [none, hardware, software]")


        CommConfig.get_from_console(self)

    def display_config(self):
        PARITY = ['none', 'odd', 'even']
        FLOW_CONTROL = ['none', 'hardware', 'software']

        CommConfig.display_config(self)
        print( "Device OS Port: " + str(self.device_os_port ))
        print( "Device Baud: " + str(self.device_baud ))
        print( "Device Data Bits: " + str(self.device_data_bits ))
        print( "Device Parity: " + PARITY[self.device_parity])
        print( "Device Stop Bits: " + str(self.device_stop_bits ))
        print( "Device Flow Control: " + FLOW_CONTROL[self.device_flow_control])

    def _config_dictionary(self):
        config = CommConfig._config_dictionary(self)
        config['device_os_port'] = self.device_os_port
        config['device_baud'] = int(self.device_baud)
        config['device_data_bits'] = int(self.device_data_bits)
        config['device_parity'] = int(self.device_parity)
        config['device_stop_bits'] = int(self.device_stop_bits)
        config['device_flow_control'] = int(self.device_flow_control)

        return config


# List of all known CommConfig objects
_CONFIG_OBJECTS = [ CommConfigEthernet, CommConfigBOTPT, CommConfigSerial ]


if __name__ == '__main__':
    pass
