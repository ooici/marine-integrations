#!/usr/bin/env python

"""
@file coi-services/mi/idk/platform/driver_generator.py
@author Bill French
@brief Generate directory structure and code stubs for a driver
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'


import os
import sys
import re
from string import Template
import random
import string
import shutil

from mi.core.log import get_logger ; log = get_logger()
from mi.idk import prompt
from mi.idk.config import Config
from mi.idk.platform.metadata import Metadata
import mi.idk.driver_generator

from mi.idk.exceptions import DriverParameterUndefined
from mi.idk.exceptions import MissingTemplate

class DriverGenerator(mi.idk.driver_generator.DriverGenerator):
    """
    Generate driver code, tests and directory structure
    """

    ###
    #    Configurations
    ###
        
    def driver_base_dir(self):
        """
        @brief full path to the driver make dir
        @retval driver make path
        """
        if not self.metadata.driver_path:
            log.info("metadata is %s", self.metadata)
            raise DriverParameterUndefined("driver_path undefined in metadata")
        
        return os.path.join(Config().base_dir(),
                            "mi", "platform", "driver")

    def driver_dir(self):
        """
        @brief full path to the driver code
        @retval driver path
        """
        if not self.metadata.driver_path:
            raise DriverParameterUndefined("driver_path undefined in metadata")
        
        return os.path.join(self.driver_base_dir(),self.metadata.driver_path)

    def template_dir(self):
        """
        @brief path to the driver template dir
        @retval driver test code template path
        """
        return os.path.join(Config().template_dir(), 'platform')

    def driver_name_camelcase(self):
        """
        @brief full instrument name with first letter capitalized
        @retval full instrument name with first letter capitalized
        """
        return string.capwords(self.metadata.driver_name, '_').replace('_','')

    ###
    #   Private Methods
    ###
    def __init__(self, metadata, force = False):
        """
        @brief Constructor
        @param metadata IDK Metadata object
        """
        mi.idk.driver_generator.DriverGenerator.__init__(self, metadata, force)

        self.metadata = metadata
        self.force = force

    def _driver_template_data(self):
        """
        @brief dictionary containing a map of substitutions for the driver code generation
        @retval data mapping for driver generation
        """
        return {
            'driver_module': self.driver_modulename(),
            'file': self.driver_relative_path(),
            'author': self.metadata.author,
            'driver_name': self.metadata.driver_name,
            'driver_path': self.metadata.driver_path,
            'release_notes': self.metadata.notes,
            'constructor': self.metadata.constructor,
            'full_instrument_lower': self.metadata.driver_name.lower(),
            'full_instrument_camelcase': self.driver_name_camelcase(),
        }

    def _test_template_data(self):
        """
        @brief dictionary containing a map of substitutions for the driver test code generation
        @retval data mapping for driver test generation
        """
        chars=string.ascii_uppercase + string.digits
        id = ''.join(random.choice(chars) for x in range(6))

        return {
            'test_module': self.test_modulename(),
            'driver_module': self.driver_modulename(),
            'driver_dir': self.driver_dir(),
            'file': self.driver_relative_path(),
            'author': self.metadata.author,
            'driver_name': self.metadata.driver_name,
            'constructor': self.metadata.constructor,
            'full_instrument_lower': self.metadata.driver_name.lower(),
            'full_instrument_camelcase': self.driver_name_camelcase(),
        }


    def create_init_files(self):
        path = self.driver_test_dir()
        p = os.path.join(self.metadata.driver_path, 'test')
        for part in p.split('/'):
            self._touch_init(path)
            path = os.path.join(path, '..')

