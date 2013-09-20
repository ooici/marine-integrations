"""
@file coi-services/mi.idk.dataset/package_driver.py
@author Emily Hahn
@brief Main script class for running the package_driver process
"""
import os
import sys
import subprocess
import shutil

from mi.core.log import get_logger ; log = get_logger()

import mi.idk.package_driver
from mi.idk.exceptions import InvalidParameters
from mi.idk import prompt
from mi.idk.dataset.metadata import Metadata
from mi.idk.dataset.nose_test import NoseTest
from mi.idk.dataset.driver_generator import DriverGenerator
from mi.idk.dataset.egg_generator import EggGenerator

REPODIR = '/tmp/repoclone'

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
        self._zipfile = None
        self._manifest = None
        self._compression = None

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
        
    def clone_repo(self):
        """
        clone the ooici repository into a temp location and navigate to it
        """
        # make a temp dir to put the clone in
        if not os.path.exists(REPODIR):
            os.mkdir(REPODIR)
        os.chdir(REPODIR)
        # remove an old clone if one exists, start clean
        if os.path.exists(REPODIR + '/marine-integrations'):
            shutil.rmtree(REPODIR + '/marine-integrations')

        # clone the ooici repository into a temporary location
        os.system('git clone git@github.com:ooici/marine-integrations.git')
        log.debug('cloned repository')

        # if the directory doesn't exist, something went wrong with cloning
        if not os.path.exists(REPODIR + '/marine-integrations'):
            raise InvalidParameters('Error creating ooici repository clone')
        # navigate into the cloned repository
        os.chdir(REPODIR + '/marine-integrations')
        log.debug('in cloned repository')

        # get which dataset agent is selected from the current metadata, use
        # this to get metadata from the cloned repo
        tmp_metadata = Metadata()
        # read metadata from the cloned repo
        self.metadata = Metadata(tmp_metadata.driver_path, REPODIR + '/marine-integrations')

    def get_repackage_version(self):
        """
        Get the driver version the user wants to repackage
        """
        # suggest the current driver version as default
        repkg_version = prompt.text( 'Driver Version to re-package', self.metadata.version )
        # check to make sure this driver version exists
        tag_name = 'driver_' + self.metadata.driver_name + '_' + repkg_version.replace('.','_')
        cmd = 'git tag -l ' + tag_name 
        # find out if this tag name exists
        output = subprocess.check_output(cmd, shell=True)
        if len(output) > 0:
            # this tag exists, check it out
            os.system('git checkout tags/' + tag_name)
            # re-read the metadata since version may have changed in metadata.yml file
            self.metadata = Metadata(self.metadata.driver_path, REPODIR + '/marine-integrations')
        else:
            log.error('No driver version %s found', tag_name)
            raise InvalidParameters('No driver version %s found', tag_name)

    def make_branch(self):
        """
        Make a new branch for this release and tag it with the same name so we
        can get back to it
        """
        name = self.metadata.driver_name_versioned
        # create a new branch name and check it out
        cmd = 'git checkout -b ' + name
        output = subprocess.check_output(cmd, shell=True)
        log.debug('created new branch %s: %s', name, output)
        # tag the initial branch so that we can get back to it later
        cmd = 'git tag ' + name
        output = subprocess.check_output(cmd, shell=True)
        log.debug('created new tag %s: %s', name, output)

    def update_version(self):
        """
        Update the driver version for this package.  By default increment by one.
        After updating the metadata file, commit the change to git.
        """
        last_dot = self.metadata.version.rfind('.')
        last_version = int(self.metadata.version[last_dot+1:])
        suggest_version = self.metadata.version[:last_dot+1] + str(last_version + 1)
        new_version = prompt.text('Update Driver Version', suggest_version )
        if new_version != self.metadata.version:
            # set the new driver version in the metadata
            self.metadata.set_driver_version(new_version)
            # commit the changed file to git
            cmd = 'git commit ' + str(self.metadata.metadata_path()) + ' -m \'Updated metadata driver version\''
            os.system(cmd)
            # read metadata again to update the version in our metadata
            self.metadata = Metadata(self.metadata.driver_path, REPODIR + '/marine-integrations')

    def run(self):
        print "*** Starting Driver Packaging Process ***"
        
        # store the original directory since we will be navigating away from it
        original_dir = os.getcwd()

        # first create a temporary clone of ooici to work with
        self.clone_repo()

        # for now comment out the test option until test are more stable,
        # just build the package driver
        if len(sys.argv) == 2 and (sys.argv[1] == "--repackage"):
            self.get_repackage_version()
            self.package_driver()
        else:
            self.update_version()
            self.make_branch()
            self.package_driver()

            if prompt.yes_no('Do you want to push the new release branch to ooici?'):
                cmd = 'git push'
                output = subprocess.check_output(cmd, shell=True)
                if len(output) > 0:
                    log.debug('git push returned: %s', output)

        # go back to the original directory
        os.chdir(original_dir)

        print "Package Created: " + self.archive_path()

    ###
    #   Private Methods
    ###
    def _store_package_files(self):
        """
        @brief Store all files in zip archive and add them to the manifest file
        """
        self.generator = DriverGenerator(self.metadata)
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




