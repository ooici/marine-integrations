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

    def update_version(self):
        """
        Update the driver version for this package.  By default increment by one.
        After updating the metadata file, commit the change to git.
        """
        last_dot = self.metadata.version.rfind('.')
        last_version = int(self.metadata.version[last_dot+1:])
        suggest_version = self.metadata.version[:last_dot+1] + str(last_version + 1)
        new_version = prompt.text('Update Driver Version', suggest_version )
        # make sure the entered version has the correct format
        self._verify_version(new_version)
        if new_version != self.metadata.version:
            # search for the tag for this version, find out if it already exists
            cmd = 'git tag -l ' + 'driver_' + self.metadata.driver_name + '_' + new_version.replace('.', '_')
            # find out if this tag name exists
            output = subprocess.check_output(cmd, shell=True)
            if len(output) > 0:
                # this tag already exists and we are not repackaging
                raise InvalidParameters("Version %s already exists.  To repackage, run package driver with the --repackage option", new_version)

            # set the new driver version in the metadata
            self.metadata.set_driver_version(new_version)
            # commit the changed file to git
            cmd = 'git commit ' + str(self.metadata.metadata_path()) + ' -m \'Updated metadata driver version\''
            os.system(cmd)

        return new_version

    def run(self):
        print "*** Starting Driver Packaging Process ***"

        # store the original directory since we will be navigating away from it
        original_dir = os.getcwd()

        # first create a temporary clone of ooici to work with
        self.clone_repo()

        # get which dataset agent is selected from the current metadata, use
        # this to get metadata from the cloned repo
        tmp_metadata = Metadata()
        # read metadata from the cloned repo
        self.metadata = Metadata(tmp_metadata.driver_path, REPODIR + '/marine-integrations')

        # for now leave out the test option until test are more stable,
        # just build the package driver
        if len(sys.argv) == 2 and (sys.argv[1] == "--repackage"):
            self.get_repackage_version('driver_' + self.metadata.driver_name)
            self.package_driver()
        else:
            new_version = self.update_version()
            self.make_branch('driver_' + self.metadata.driver_name + '_' + new_version.replace('.', '_'))
            self.package_driver()

            #if not "--no-push" in sys.argv:
            #    cmd = 'git push'
            #    output = subprocess.check_output(cmd, shell=True)
            #    if len(output) > 0:
            #        log.debug('git push returned: %s', output)

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
        self.metadata = Metadata(self.metadata.driver_path, REPODIR + '/marine-integrations')
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

    def _store_resource_files(self):
        """
        @brief Store additional files added by the driver developer.  These
        files live in the driver resource dir.
        """
        resource_dir = os.path.join(self.metadata.relative_driver_path(), "resource")
        log.debug(" -- Searching for developer added resource files in dir: %s",
                  resource_dir)
        stringfile = self.string_file()
        if os.path.exists(resource_dir):
            for file in os.listdir(resource_dir):
                if file != stringfile:
                    log.debug("    ++ found: " + file)
                    desc = prompt.text('Describe ' + file)
                    self._add_file(resource_dir + "/" + file, 'resource', desc)
        else:
            log.debug(" --- No resource directory found, skipping...")
    
if __name__ == '__main__':
    app = PackageDriver()
    app.run()




