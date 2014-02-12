#!/usr/bin/env python

"""
@file coi-services/mi/idk/dataset/metadata.py
@author Bill French
@brief Gather and store metadata for driver creation
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import sys
import os
import errno

import yaml

from mi.core.log import get_logger ; log = get_logger()

import mi.idk.metadata

from mi.idk import prompt
from mi.idk.config import Config

from mi.idk.exceptions import DriverParameterUndefined
from mi.idk.exceptions import UnknownDriver
from mi.idk.exceptions import InvalidParameters

class Metadata(mi.idk.metadata.Metadata):
    """
    Gather and store metadata for the IDK driver creation process.  When the metadata is stored it also creates a link
    to current .yml in the config dir.  That symlink indicates which driver you are currently working on.
    """

    ###
    #   Configuration
    ###
    def driver_dir(self):
        """
        @brief full path to the driver code
        @retval driver path
        """
        if not self.driver_path:
            raise DriverParameterUndefined("driver_path undefined in metadata")

        return os.path.join(self.base_dir, self.relative_driver_path())

    def relative_driver_path(self):
        """
        @brief return driver path relative to mi
        """
        return os.path.join("mi", "dataset", "driver",
                            self.driver_path)

    def resource_dir(self):
        """
        @brief full path to the driver resource directory
        @retval resource path
        """
        return os.path.join(self.driver_dir(), 'resource')

    def idk_dir(self):
        """
        @brief directory to store the idk driver configuration
        @retval dir name 
        """
        return Config().idk_config_dir()

    def metadata_filename(self):
        """
        @brief metadata file name
        @retval filename
        """
        return "metadata.yml"

    def metadata_path(self):
        """
        @brief path to the metadata config file
        @retval metadata path
        """
        return self.driver_dir() + "/" + self.metadata_filename()

    def current_metadata_path(self):
        """
        @brief path to link the current metadata file
        @retval current metadata path
        """
        return self.idk_dir() + "/current_dsa.yml"

    def set_driver_version(self, version):
        """
        @brief set the driver version
        """
        self.version = version
        self.store_to_file()

    ###
    #   Private Methods
    ###
    def __init__(self, driver_path = None, base_dir = Config().base_dir()):
        """
        @brief Constructor
        """
        self.author = None
        self.email = None
        self.driver_path = driver_path
        self.driver_name = None
        self.notes = None
        self.version = 0
        self.base_dir = base_dir
        self.constructor = None
        self.driver_name_versioned = None
        self.entry_point_group = None
        self.versioned_constructor = None
        
        log.debug("Constructing dataset metadata")

        if(driver_path):
            log.debug("Construct from parameters: %s", self.metadata_path())
            if(os.path.isfile(self.metadata_path())):
                self.read_from_file(self.metadata_path())
            
        elif(not(driver_path)):
            self.read_from_file()
            
        else:
            raise InvalidParameters(msg="driver_path must all be specified")

    def _init_from_yaml(self, yamlInput):
        """
        @brief initialize the object from YAML data
        @param data structure with YAML input
        """
        log.info("YML Config: %s", yamlInput)
        self.author = yamlInput['driver_metadata'].get('author')
        self.email = yamlInput['driver_metadata'].get('email')
        self.driver_path = yamlInput['driver_metadata'].get('driver_path')
        self.driver_name = yamlInput['driver_metadata'].get('driver_name')
        self.notes = yamlInput['driver_metadata'].get('release_notes')
        self.version = yamlInput['driver_metadata'].get('version', 0)
        # constructor must match driver class constructor name in driver.py
        self.constructor = yamlInput['driver_metadata'].get('constructor')
        self._generate_versioned_metadata()

    def _generate_versioned_metadata(self):
        """
        Generate a set of versioned metadata variables which combine other entered variables
        """
        self.driver_name_versioned = 'dsd_%s_%s' % (self.driver_name,
                                                    self.version.replace('.','_').replace('-','_'))
        self.entry_point_group = 'drivers.dataset.%s' % self.driver_name
        # This assumes the name of the driver file is 'driver.py'
        self.versioned_constructor = 'driver-%s = %s.mi.dataset.driver.%s.driver:%s' % (self.version,
                                                                                        self.driver_name_versioned,
                                                                                        self.driver_path.replace('/', '.'),
                                                                                        self.constructor)

    ###
    #   Public Methods
    ###
    def display_metadata(self):
        """
        @brief Pretty print the current metadata object to STDOUT
        """
        print( "Driver Path: " + self.driver_path )
        print( "Driver Name: " + self.driver_name )
        print( "Author: " + self.author )
        print( "Email: " + self.email )
        print( "Release Notes: \n" + self.notes )
        print( "Driver Version: \n" + self.version )
        print( "Driver Constructor: \n" + self.constructor )
        print( "Driver Entry Point Group: \n" + self.entry_point_group )
        print( "Driver Versioned Constructor: \n" + self.versioned_constructor )

    def serialize(self):
        """
        @brief Serialize metadata object data into a yaml string.
        @retval yaml string
        """
        return yaml.dump( {'driver_metadata': {
                            'author': self.author,
                            'email': self.email,
                            'driver_path': self.driver_path,
                            'driver_name': self.driver_name,
                            'release_notes': self.notes,
                            'version': self.version,
                            'constructor': self.constructor,
                          }
        }, default_flow_style=False)

    def get_from_console(self):
        """
        @brief Read metadata from the console and initialize the object.  Continue to do this until we get valid input.
        """
        self.driver_path = prompt.text( 'Driver Path', self.driver_path )
        self.driver_name = prompt.text( 'Driver Name', self.driver_name )
        self.version = prompt.text( 'Driver Version', self.version )
        self.author = prompt.text( 'Author', self.author )
        self.email = prompt.text( 'Email', self.email )
        self.notes = prompt.multiline( 'Release Notes', self.notes )
        # constructor must match driver class constructor name in driver.py
        self.constructor = prompt.text( 'Driver Constructor', self.constructor )
        self._generate_versioned_metadata()

        if( self.confirm_metadata() ):
            self.store_to_file()
        else:
            return self.get_from_console()


if __name__ == '__main__':
    metadata = Metadata()
    metadata.get_from_console()
