#!/usr/bin/env python

"""
@file coi-services/mi/idk/dataset/driver_generator.py
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
from mi.idk.dataset.metadata import Metadata
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
                            "mi", "dataset", "driver")

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
        return os.path.join(Config().template_dir(), 'dsa')

    def parser_filename(self):
        """
        @brief file name of the parser
        @retval parser filename
        """
        return "%s.py" % self.metadata.driver_name.lower()

    def parser_test_filename(self):
        """
        @brief file name of the parser tests
        @retval parser test filename
        """
        return "test_%s.py" % self.metadata.driver_name.lower()

    def parser_dir(self):
        """
        @brief full path to parser code
        @retval parser path
        """
        return os.path.join(Config().base_dir(), "mi", "dataset", "parser")

    def parser_test_dir(self):
        """
        @brief full path to parser test code
        @retval parser test path
        """
        return os.path.join(Config().base_dir(), "mi", "dataset", "parser", "test")

    def parser_path(self):
        """
        @brief full path and filename to the parser code
        @retval parser path and filename
        """
        return os.path.join(self.parser_dir(), self.parser_filename())

    def parser_test_path(self):
        """
        @brief full path and filename to the parser code
        @retval parser path and filename
        """
        return os.path.join(self.parser_test_dir(), self.parser_test_filename())

    def parser_template(self):
        """
        @brief path to the  parser code template
        @retval parser code template path
        """
        return os.path.join(self.template_dir(), "parser.tmpl")

    def parser_test_template(self):
        """
        @brief path to the  parser test code template
        @retval parser test code template path
        """
        return os.path.join(self.template_dir(), "parser_test.tmpl")

    def parser_modulename(self):
        """
        @brief module name of the new driver tests
        @retval driver test module name
        """
        return self.parser_path().replace(Config().base_dir() + "/",'').replace('/','.').replace('.py','')

    def parser_test_modulename(self):
        """
        @brief module name of the new driver tests
        @retval driver test module name
        """
        return self.parser_test_path().replace(Config().base_dir() + "/",'').replace('/','.').replace('.py','')

    def parser_relative_path(self):
        """
        @brief relative path and filename to the parser code
        @retval driver path
        """
        return re.sub('.*?marine-integrations', 'marine-integrations', self.parser_path())

    def parser_test_relative_path(self):
        """
        @brief relative path and filename to the parser code
        @retval driver path
        """
        return re.sub('.*?marine-integrations', 'marine-integrations', self.parser_test_path())

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

    def _parser_template_data(self):
        """
        @brief dictionary containing a map of substitutions for the driver code generation
        @retval data mapping for driver generation
        """
        return {
            'driver_module': self.parser_modulename(),
            'file': self.parser_relative_path(),
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

    def _parser_test_template_data(self):
        """
        @brief dictionary containing a map of substitutions for the driver test code generation
        @retval data mapping for driver test generation
        """
        chars=string.ascii_uppercase + string.digits
        id = ''.join(random.choice(chars) for x in range(6))

        return {
            'test_module': self.parser_test_modulename(),
            'driver_module': self.parser_modulename(),
            'driver_dir': self.parser_dir(),
            'file': self.parser_test_relative_path(),
            'author': self.metadata.author,
            'driver_name': self.metadata.driver_name,
            'full_instrument_lower': self.metadata.driver_name.lower(),
            'full_instrument_camelcase': self.driver_name_camelcase()
        }


    ###
    #   Public Methods
    ###
    def build_directories(self):
        """
        @brief Build directory structure for the new driver
        """
        print( " -- Build directories --" )

        if not os.path.exists(self.driver_dir()):
            os.makedirs(self.driver_dir())

        if not os.path.exists(self.driver_test_dir()):
            os.makedirs(self.driver_test_dir())

        if not os.path.exists(self.resource_dir()):
            os.makedirs(self.resource_dir())

        if not os.path.exists(self.parser_dir()):
            os.makedirs(self.parser_dir())
            self._touch_init(self.parser_dir())

        if not os.path.exists(self.parser_test_dir()):
            os.makedirs(self.parser_test_dir())
            self._touch_init(self.parser_dir())

        path = self.driver_test_dir()
        p = os.path.join(self.metadata.driver_path, 'test')
        for part in p.split('/'):
            self._touch_init(path)
            path = os.path.join(path, '..')

    def generate_code(self):
        """
        @brief Generate code files for the driver and tests
        """
        print( " -- Generating code --" )
        self.generate_driver_code()
        self.generate_parser_code()
        self.generate_test_code()
        self.generate_parser_test_code()
        self.generate_resource_files()

    def generate_parser_code(self):
        """
        @brief Generate stub parser code
        """
        if(os.path.exists(self.parser_path()) and not self.force):
            msg = "Warning: driver exists (" + self.parser_path() + ") not overwriting"
            sys.stderr.write(msg)
            log.warn(msg)
        else:
            log.info("Generate parser code from template %s to file %s" % (self.parser_template(),
                                                                           self.parser_path()))

            template = self._get_template(self.parser_template())
            ofile = open( self.parser_path(), 'w' )
            code = template.substitute(self._parser_template_data())
            ofile.write(code)
            ofile.close()

    def generate_parser_test_code(self):
        """
        @brief Generate stub parser test code
        """
        if(os.path.exists(self.parser_test_path()) and not self.force):
            msg = "Warning: driver exists (" + self.parser_test_path() + ") not overwriting"
            sys.stderr.write(msg)
            log.warn(msg)
        else:
            log.info("Generate parser code from template %s to file %s" % (self.parser_test_template(),
                                                                           self.parser_test_path()))

            template = self._get_template(self.parser_test_template())
            ofile = open( self.parser_test_path(), 'w' )
            code = template.substitute(self._parser_test_template_data())
            ofile.write(code)
            ofile.close()


if __name__ == '__main__':
    metadata = Metadata()
    driver = DriverGenerator( metadata )

    driver.generate()

