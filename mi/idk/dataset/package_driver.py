"""
@file coi-services/mi.idk.dataset/package_driver.py
@author Emily Hahn
@brief Main script class for running the package_driver process
"""
import os
import sys
import subprocess

from mi.core.log import get_logger ; log = get_logger()

import mi.idk.package_driver
from mi.idk.exceptions import InvalidParameters

from mi.idk.dataset.metadata import Metadata
from mi.idk.dataset.nose_test import NoseTest
from mi.idk.dataset.driver_generator import DriverGenerator
from mi.idk.dataset.egg_generator import EggGenerator

class PackageDriver(mi.idk.package_driver.PackageDriver):

    def archive_file(self):
        return "%s-%s-driver.zip" % (self.metadata.driver_name,
                                     self.metadata.version)
    
    ###
    #   Public Methods
    ###
    def __init__(self):
        """
        @brief ctor
        """
        self.metadata = Metadata()
        self._zipfile = None
        self._manifest = None
        self._compression = None
        self.generator = DriverGenerator(self.metadata)

        # Set compression level
        self.zipfile_compression()
        
    def run_qualification_tests(self):
        """
        @brief Run all qualification tests for the driver and store the results for packaging
        """
        log.info("-- Running qualification tests")

        test = NoseTest(self.metadata, log_file=self.log_path())
        test.report_header()

        if(test.run_qualification()):
            log.info(" ++ Qualification tests passed")
            return True
        else:
            log.error("Qualification tests have fail!  No package created.")
            return False
        
    def get_repackage_version(self):
        """
        Get the driver version the user wants to repackage
        """
        # suggest the current driver version as default
        repkg_version = prompt.text( 'Driver Version to re-package', self.metadata.version )
        # check to make sure this driver version exists
        tag_name = self.metadata.driver_name + '_' + repkg_version
        cmd = 'git tag -l ' + tag_name 
        # find out if this tag name exists
        output = subprocess.check_output(cmd, shell=True)
        if len(output) > 0:
            # this tag exists, check it out
            os.system('git checkout tags/' + tag_name)
            # re-read the metadata since we may have changed the metadata.yml file
            self.metadata = Metadata()
        else:
            log.error('No driver version %s found', tag_name)
            raise InvalidParameters('No driver version %s found', tag_name)
            
    def make_branch(self):
        """
        Make a new branch for this release and tag it with the same name so we
        can get back to it
        """
        name = self.metadata.driver_name_versioned
        # make sure there are no modified files
        cmd = 'git diff --name-only --ignore-submodules'
        output = subprocess.check_output(cmd, shell=True)
        if len(output) > 0:
            log.error('There are uncommitted changes, please commit all changes before running package_driver')
            raise InvalidParameters('There are uncommitted changes, please commit all changes before running package driver')
        # create a new branch name and check it out
        cmd = 'git checkout -b ' + name
        output = subprocess.check_output(cmd, shell=True)
        if len(output) > 0:
            log.debug('new branch checkout returned: %s', output)
        log.debug('created new branch %s', name)
        # tag the initial branch so that we can get back to it later
        cmd = 'git tag ' + name
        output = subprocess.check_output(cmd, shell=True)
        if len(output) > 0:
            log.debug('tag create returned: %s', output)
        log.debug('create new tag %s', name)
        
    def run(self):
        print "*** Starting Driver Packaging Process ***"
        
        # for now comment out the test option until test are more stable,
        # just build the package driver
        if len(sys.argv) == 2 and (sys.argv[1] == "--repackage"):
            self.get_repackage_version()
            self.package_driver()
        else:
            self.update_version()
            self.make_branch()
            self.package_driver()
        #if len(sys.argv) == 2 and (sys.argv[1] == "--no-test"):
            # clear the log file so it exists
            #f = open(self.log_path(), "w")
            #f.write("Tests manually bypassed with --no-test option\n")
            #f.close()
            #self.package_driver()
        #else:
        #    if(self.run_qualification_tests()):
        #        self.package_driver()

        print "Package Created: " + self.archive_path()
        
    ###
    #   Private Methods
    ###
    def _store_package_files(self):
        """
        @brief Store all files in zip archive and add them to the manifest file
        """

        egg_generator = EggGenerator(self.metadata)
        egg_file = egg_generator.save()

        # Add egg
        self._add_file(egg_file, 'egg', 'python driver egg package')

        # Add the package metadata file
        self._add_file(self.metadata.metadata_path(), description = 'package metadata')

        # Add the qualification test log
        self._add_file(self.log_path(), description = 'qualification tests results')

        # Store parameter/command string description file
        self._add_file("%s/%s" % (self.generator.resource_dir(), self.string_file()),
                       'resource', 'driver string file')
        
        # Store additional resource files
        self._store_resource_files()

        # Finally save the manifest file.  This must be last of course
        self._add_file(self.manifest().manifest_path(), description = 'package manifest file')
    
if __name__ == '__main__':
    app = PackageDriver()
    app.run()




