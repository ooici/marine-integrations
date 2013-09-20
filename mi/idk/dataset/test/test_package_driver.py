#!/usr/bin/env python

"""
@package mi.idk.dataset.test.test_package_driver
@file mi.idk/dataset/test/test_package_driver.py
@author Emily Hahn
@brief test package driver object
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

from mi.core.unit_test import MiUnitTest

from mi.core.log import get_logger ; log = get_logger()
from nose.plugins.attrib import attr

import sys
import os
import re
import pkg_resources
from os.path import exists

from mi.idk.config import Config

from mi.idk.dataset.metadata import Metadata
from mi.idk.dataset.package_driver import PackageDriver

MI_BASE_DIR = "mi/dataset/driver"
DRIVER_DIR = "fake_platform/fake_driver"
CONSTRUCTOR = "FakeDriver"
METADATA_FILE = "metadata.yml"

@attr('UNIT', group='mi')
class TestPackageDriver(MiUnitTest):

    def setUp(self):
        """
        Setup the test case
        """
        # create the expected file and directories to go with the metadata
        self.createFakeDriver()

    def createMetadataFile(self, version="0.2.2"):
        """
        Copied from test_metadata
        """

        full_driver_path = "%s/%s/%s" % (Config().base_dir(), MI_BASE_DIR, DRIVER_DIR)
        if(not exists(full_driver_path)):
            os.makedirs(full_driver_path)
        md_file_path = "%s/%s" % (full_driver_path, METADATA_FILE)
        md_file = open(md_file_path, 'w')

        md_file.write("driver_metadata:\n")
        md_file.write("  author: Bill French\n")
        path_str = "  driver_path: %s\n" % DRIVER_DIR
        md_file.write(path_str)
        md_file.write("  driver_name: fake_driver\n")
        md_file.write("  email: wfrench@ucsd.edu\n")
        md_file.write("  release_notes: some note\n")
        version_str = "  version: %s\n" % version
        md_file.write(version_str)
        constr_str = "  constructor: %s\n" % CONSTRUCTOR
        md_file.write(constr_str)

        md_file.close()
        
        current_dsa_path = Config().idk_config_dir() + "/current_dsa.yml"
        log.info("linking %s to %s", md_file_path, current_dsa_path)
        # exists doesn't catch when this link is broken but still there,
        # need to figure out how to find and delete
        if exists(current_dsa_path):
            os.remove(current_dsa_path)
        
        os.symlink(md_file_path, current_dsa_path)
            
    def createFakeDriver(self):
        """
        Write a fake driver
        """
        full_driver_path = "%s/%s/%s" % (Config().base_dir(), MI_BASE_DIR, DRIVER_DIR)
        if(not exists(full_driver_path)):
            os.makedirs(full_driver_path)
        
        fake_driver_path = "%s/%s/%s/driver.py" % (Config().base_dir(), MI_BASE_DIR, DRIVER_DIR)
        
        # create a fake driver file
        if not exists(fake_driver_path):
            # write a make driver which just has the class constructor in it
            fake_driver_file = open(fake_driver_path, 'w')
            log.info("creating fake driver %s", fake_driver_path)
            fake_driver_file.write("from mi.core.log import get_logger ; log = get_logger()\n\n")
            class_line = "class %s(object):\n\n" % CONSTRUCTOR 
            fake_driver_file.write(class_line)
            fake_driver_file.write("    def sayHello(self):\n")
            fake_driver_file.write("        log.info('Hello from Dataset Driver')\n")
            fake_driver_file.close()
            
            # make sure we have __init__.py in both dirs
            init_path = "%s/%s/%s/__init__.py" % (Config().base_dir(), MI_BASE_DIR, "fake_platform")
            touch = open(init_path, "w")
            touch.close()
            init_path = "%s/%s/%s/__init__.py" % (Config().base_dir(), MI_BASE_DIR, DRIVER_DIR)
            touch = open(init_path, "w")
            touch.close()
            
        else:
            log.info("fake driver already initialized %s", fake_driver_path)
        
        # make sure there is a test directory
        test_dir_path = "%s/%s/%s/test" % (Config().base_dir(), MI_BASE_DIR, DRIVER_DIR)
        if not exists(test_dir_path):
            os.makedirs(test_dir_path)
            
        # make sure there is a resource directory
        resource_dir_path = "%s/%s/%s/resource" % (Config().base_dir(), MI_BASE_DIR, DRIVER_DIR)
        if not exists(resource_dir_path):
            os.makedirs(resource_dir_path)
        
        # the resource directory must contain strings.yml
        resource_path = "%s/strings.yml" % resource_dir_path
        if not exists(resource_path):
            touch = open(resource_path, "w")
            touch.close()
            
        test_driver_path = "%s/test_driver.py" % test_dir_path
        if not exists(test_driver_path):
            fake_driver_test = open(test_driver_path, 'w')
            log.info("creating fake test driver %s", test_driver_path)
            fake_driver_test.close()
            # make sure we have an __init__.py
            init_path = "%s/__init__.py" % test_dir_path
            touch = open(init_path, "w")
            touch.close()
        else:
            log.info("fake test driver test already initialized")
        
    #def test_package_driver(self):
        """
        # make a metadata file is initialized, otherwise it might not exist 
        self.createMetadataFile()
        
        # create the metadata so we can use it for opening the egg 
        metadata1 = Metadata()
        
        package_driver = PackageDriver()
        package_driver.run()
        
        # overwrite the original metadata file for the same driver and change the version
        self.createMetadataFile("0.2.5")
        
        # create the metadata so we can use it for opening the egg 
        metadata2 = Metadata()
        
        # run package driver again to create the new driver version
        package_driver = PackageDriver()
        package_driver.run()
        
        log.info("Both driver eggs created")
        
        # load the first driver
        cotr1 = self.load_egg(metadata1)
        loaded_driver = cotr1()
        loaded_driver.sayHello()
        log.info("First driver done saying hello")
        
        # load the second driver
        cotr2 = self.load_egg(metadata2)
        loaded_driver2 = cotr2()
        loaded_driver2.sayHello()
        log.info("Second driver done saying hello")
        
        # just print out some entry point info
        for x in pkg_resources.iter_entry_points('drivers.dataset.fake_driver'):
            log.info("entry point:%s", x)
        """   
    def test_package_driver_real(self):
        """
        Test with real hypm ctd driver code
        """
        
        # link current metadata dsa file to a real driver, the ctd
        current_dsa_path = Config().idk_config_dir() + "/current_dsa.yml"
        ctd_md_path = "%s/%s/hypm/ctd/metadata.yml" % (Config().base_dir(), MI_BASE_DIR)
        log.info("linking %s to %s", ctd_md_path, current_dsa_path)
        # exists doesn't catch when this link is broken but still there,
        # need to figure out how to find and delete
        if exists(current_dsa_path):
            os.remove(current_dsa_path)
        
        os.symlink(ctd_md_path, current_dsa_path)
        
        # create the metadata so we can use it for opening the egg 
        metadata = Metadata()
    
        # create the egg with the package driver
        package_driver = PackageDriver()
        package_driver.run()
        
        startup_config = {
            'harvester':
            {
                'directory': '/tmp/dsatest',
                'pattern': '*.txt',
                'frequency': 1,
            },
            'parser': {}
        }

        # load the driver
        cotr = self.load_egg(metadata)
        # need to load with the right number of arguments
        egg_driver = cotr(startup_config, None, None, None, None)
        log.info("driver loaded")
        
        
    def load_egg(self, metadata):
        # use metadata to initialize egg name and location, but only the egg name
        # should be used to figure out how to load the entry point
        egg_name = "%s-%s-py2.7.egg" % (metadata.driver_name_versioned, metadata.version)
        egg_cache_dir = "/tmp/%s/dist" % metadata.driver_name_versioned
        pkg_resources.working_set.add_entry(egg_cache_dir + '/' + egg_name)
        first_dash_idx = egg_name.find('-')
        second_dash_idx = egg_name[first_dash_idx+1:].find('-')
        first_under_idx = egg_name.find('_')
        driver_name = egg_name[first_under_idx+1:first_dash_idx]
        log.debug("found driver name %s", driver_name)
        digit_match = re.search("\d", driver_name)
        if digit_match:
            first_digit = digit_match.start()
            short_driver = driver_name[:first_digit-1]
        else:
            short_driver = driver_name
        log.debug("found short driver name %s", short_driver)
        version = egg_name[first_dash_idx+1:(second_dash_idx+first_dash_idx+1)]
        log.debug("found version %s", version)
        entry_point = 'driver-' + version
        group_name = 'drivers.dataset.' + short_driver
        log.info("entry point %s, group_name %s", entry_point, group_name)
        cotr = pkg_resources.load_entry_point('driver_' + driver_name, group_name, entry_point)
        log.info("loaded entry point")
        return cotr
        
    
        
        
    


