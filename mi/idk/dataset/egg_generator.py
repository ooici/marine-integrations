#!/usr/bin/env python

"""
@file coi-services/mi.idk.dataset/egg_generator.py
@author Emily Hahn
@brief Generate egg for a dataset agent driver.  
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

import os
import shutil
from os.path import exists, dirname
from shutil import copytree

import mi.idk.egg_generator
from mi.idk.egg_generator import DependencyList

from mi.idk.exceptions import ValidationFailure
from mi.idk.config import Config

from mi.idk.dataset.metadata import Metadata
from mi.idk.dataset.driver_generator import DriverGenerator

class DriverFileList(mi.idk.egg_generator.DriverFileList):
    """
    Build list of files that are associated to a driver.  It uses the DependencyList
    object to get all python files.  Then it will look in the target module directory
    for additional files.
    """
    def __init__(self, metadata, basedir, driver_file = None, driver_test_file = None):
        driver_generator = DriverGenerator(metadata)
        
        self.basedir = basedir

        if driver_file:
            self.driver_file = driver_file
        else:
            self.driver_file = driver_generator.driver_path()

        if driver_test_file:
            self.driver_test_file = driver_test_file
        else:
            self.driver_test_file = driver_generator.driver_test_path()

        self.driver_dependency = None
        self.test_dependency = None
        self.driver_dependency = DependencyList(self.driver_file, include_internal_init=True)
        self.test_dependency = DependencyList(self.driver_test_file, include_internal_init=True)

class EggGenerator(mi.idk.egg_generator.EggGenerator):
    """
    Generate driver egg
    """
    
    def __init__(self, metadata):
        """
        @brief Constructor
        @param metadata IDK Metadata object
        """
        self.metadata = metadata
        self._bdir = None

        if not self._tmp_dir():
            raise InvalidParameters("missing tmp_dir configuration")

        if not self._tmp_dir():
            raise InvalidParameters("missing working_repo configuration")

        self.generator = DriverGenerator(self.metadata)
        test_import = __import__(self._test_module())

    def _build_name(self):
        return self.metadata.driver_name_versioned
    
    def _generate_build_dir(self):
        build_dir = os.path.join(self._tmp_dir(), self._build_name())
        # clean out an old build if it exists
        if exists(build_dir):
            shutil.rmtree(build_dir)
        return build_dir
    
    def _driver_dir(self):
        (driver_dir, driver_fname) = os.path.split(self.metadata.driver_path)
        return driver_dir
    
    def _versioned_dir(self):
        return os.path.join(self._build_dir(),
                            self.metadata.driver_name_versioned)
    
    def _setup_path(self):
        return os.path.join(self._build_dir(), 'setup.py' )
        
    def _setup_template_path(self):
        return os.path.join(Config().template_dir(), 'dsa', 'setup.tmpl' )
    
    def _main_path(self):
        return os.path.join(self._versioned_dir(), 'mi/main.py' )
    
    def _generate_setup_file(self):
        if not os.path.exists(self._build_dir()):
            os.makedirs(self._build_dir())

        if not os.path.exists(self._build_dir()):
            raise IDKException("failed to create build dir: %s" % self._build_dir())


        setup_file = self._setup_path()
        setup_template = self._get_template(self._setup_template_path())

        log.debug("Create setup.py file: %s" % setup_file )
        log.debug("setup.py template file: %s" % self._setup_template_path())
        log.debug("setup.py template data: %s" % self._setup_template_data())

        ofile = open(setup_file, 'w')
        code = setup_template.substitute(self._setup_template_data())
        ofile.write(code)
        ofile.close()
    
    def _setup_template_data(self):
        return {
           'name': self.metadata.driver_name_versioned,
           'version': self.metadata.version,
           'description': 'ooi dataset agent driver',
           'author': self.metadata.author,
           'email': self.metadata.email,
           'url': 'http://www.oceanobservatories.org',
           'driver_module': self._driver_module(),
           'driver_class': self._driver_class(),
           'entry_point_group': self.metadata.entry_point_group,
           'versioned_constructor': self.metadata.versioned_constructor
        }
        
    def _stage_files(self, files):
        # make two levels of versioned file directories, i.e.
        #     driverA_0_1 (= build_dir)
        #         driverA_0_1
        # then copy driverA files into the bottom versioned dir
        if not os.path.exists(self._build_dir()):
            os.makedirs(self._build_dir())
        if not os.path.exists(self._versioned_dir()):
            os.makedirs(self._versioned_dir())
        
        # we need to make sure an init file is in the versioned dir so
        # that find_packages() will look in here
        init_path = self._versioned_dir() +"/__init__.py"
        if not os.path.exists(init_path):
            touch = open(init_path, "w")
            touch.close()

        for filename in files:
            # remove the first directories since we want to start from the driver platform dir
            dest = os.path.join(self._versioned_dir(), filename)
            destdir = dirname(dest)
            source = os.path.join(self._repo_dir(), filename)

            log.debug(" Copy %s => %s" % (source, dest))

            if not os.path.exists(destdir):
                os.makedirs(destdir)

            shutil.copy(source, dest)

    def _build_egg(self, files):
        try:
            self._verify_ready()
            self._stage_files(files)
            self._generate_setup_file()
            self._generate_main_file()

            cmd = "cd %s; python setup.py bdist_egg" % self._build_dir()
            log.info("CMD: %s" % cmd)
            os.system(cmd)

            egg_file = "%s/dist/%s-%s-py2.7.egg" % (self._build_dir(),
                                                    self.metadata.driver_name_versioned,
                                                    self.metadata.version)
            
            # Remove all pyc files from the egg.  There was a jira case that suggested
            # including the compiled py files caused the drivers to run slower.
            # https://jira.oceanobservatories.org/tasks/browse/OOIION-1167
            cmd = "zip %s -d \*.pyc" % egg_file
            log.info("CMD: %s" % cmd)
            os.system(cmd)

        except ValidationFailure, e:
            log.error("Failed egg verification: %s" % e )
            return None

        log.debug("Egg file created: %s" % egg_file)
        return egg_file
    
    def save(self):
        filelist = DriverFileList(self.metadata, self._repo_dir())
        return self._build_egg(filelist.files())


if __name__ == '__main__':
    pass         
