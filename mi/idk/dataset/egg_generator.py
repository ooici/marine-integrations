#!/usr/bin/env python

"""
@file coi-services/mi.idk.dataset/egg_generator.py
@author Emily Hahn
@brief Generate egg for a dataset agent driver.  
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

import string
import re
import os
import shutil
from os.path import exists, dirname
from shutil import copytree
from mi.idk import prompt
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

    def _driver_dir(self):
        (driver_dir, driver_fname) = os.path.split(self.metadata.driver_path)
        return driver_dir

    def _setup_path(self):
        return os.path.join(self._build_dir(), 'setup.py' )

    def _setup_template_path(self):
        return os.path.join(Config().template_dir(), 'dsa', 'setup.tmpl' )

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
           'entry_point_group': self.metadata.entry_point_group,
           'versioned_constructor': self.metadata.versioned_constructor,
           'driver_path': self.metadata.driver_path
        }
        
    def _stage_files(self, files):
        """
        Copy files from the original directory into two levels of versioned
        directories within a staging directory, and replace the mi namespace
        with the versioned driver name.mi to account for the new directory
        (only the lower versioned dir is included in the egg)
        @param files - a list of files to copy into the staging directory
        """
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
        init_path = self._versioned_dir() + "/__init__.py"
        if not os.path.exists(init_path):
            init_file = open(init_path, "w")
            init_file.close()
        
        for filename in files:
            # get the paths to the source and destination files
            dest = os.path.join(self._versioned_dir(), filename)
            destdir = dirname(dest)
            source = os.path.join(self._repo_dir(), filename)

            log.debug(" Copy %s => %s" % (source, dest))
            # make sure the destination directory exists, if it doesn't make it
            if not os.path.exists(destdir):
                os.makedirs(destdir)

            # copy the file
            shutil.copy(source, dest)

            # replace mi in the copied files with the versioned driver module.mi
            # this is necessary because the top namespace in the versioned files starts
            # with the versioned driver name directory, not mi
            driver_file = open(dest, "r")
            contents = driver_file.read()
            driver_file.close()
            new_contents = re.sub(r'(^import |^from |\'|= )mi\.|res/config/mi-logging|\'mi\'',
                                  self._mi_replace,
                                  contents,
                                  count=0,
                                  flags=re.MULTILINE)
            driver_file = open(dest, "w")
            driver_file.write(new_contents)
            driver_file.close()

        # need to add mi-logging.yml special because it is not in cloned repo, only in local repository
        milog = "res/config/mi-logging.yml"
        dest = os.path.join(self._versioned_dir(), milog)
        destdir = dirname(dest)
        source = os.path.join(Config().base_dir(), milog)

        log.debug(" Copy %s => %s" % (source, dest))
        # make sure the destination directory exists, if it doesn't make it
        if not os.path.exists(destdir):
            os.makedirs(destdir)

        shutil.copy(source, dest)

    def _mi_replace(self, matchobj):
        """
        This function is used in regex sub to replace mi with the versioned
        driver name followed by mi
        @param matchobj - the match object from re.sub
        """
        if matchobj.group(0) == 'res/config/mi-logging':
            return self.metadata.driver_name_versioned + '/' + matchobj.group(0)
        elif matchobj.group(0) == '\'mi\'':
            return '\'' + self.metadata.driver_name_versioned + '.mi\''
        else:
            return matchobj.group(1) + self.metadata.driver_name_versioned + '.mi.'

    def _build_egg(self, files):
        try:
            self._verify_ready()
            self._stage_files(files)
            self._generate_setup_file()

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
        driver_file = self.metadata.driver_dir() + '/' + DriverGenerator(self.metadata).driver_filename()
        driver_test_file = self.metadata.driver_dir() + '/test/' + DriverGenerator(self.metadata).driver_test_filename()
        filelist = DriverFileList(self.metadata, self._repo_dir(), driver_file, driver_test_file)
        return self._build_egg(filelist.files())


if __name__ == '__main__':
    pass         
