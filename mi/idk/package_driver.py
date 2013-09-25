"""
@file coi-services/mi.idk/package_driver.py
@author Bill French
@brief Main script class for running the package_driver process
"""

import sys
import os.path
import zipfile
import subprocess
import shutil
import re

import yaml

from mi.core.log import get_logger ; log = get_logger()
from mi.idk import prompt
from mi.idk.metadata import Metadata
from mi.idk.nose_test import NoseTest
from mi.idk.driver_generator import DriverGenerator
from mi.idk.egg_generator import EggGenerator
from mi.idk.exceptions import ValidationFailure

REPODIR = '/tmp/repoclone'

class PackageManifest(object):
    """
    Object to create and store a package file manifest
    """

    ###
    #   Configuration
    ###
    def manifest_file(self):
        return "file.lst"

    def manifest_path(self):
        return "%s/%s" % (self.metadata.idk_dir(), self.manifest_file())

    ###
    #   Public Methods
    ###
    def __init__(self, metadata):
        """
        @brief ctor
        """
        self.metadata = metadata
        self.data = {}

    def add_file(self, source, description=None):
        """
        @brief Add a file to the file manifest
        @param source path the the file in the archive
        @description one line description of the file
        """

        if(not description): description = ''

        log.debug( "  ++ Adding " + source + " to manifest")
        self.data[source] = description

        self.save()

    def serialize(self):
        """
        @brief Serialize PackageManifest object data into a yaml string.
        @retval yaml string
        """
        return yaml.dump( self.data, default_flow_style=False )

    def save(self):
        """
        @brief Write YAML file with package manifest.
        """
        outputFile = self.manifest_path()

        if not os.path.exists(self.metadata.idk_dir()):
            os.makedirs(self.metadata.idk_dir())

        ofile = open( outputFile, 'w' )

        ofile.write( self.serialize() )
        ofile.close()


class PackageDriver(object):
    """
    Main class for running the package driver process.
    """

    ###
    #   Configuration
    ###
    def string_file(self):
        return "strings.yml"
    
    def log_file(self):
        return "qualification.log"

    def log_path(self):
        return "%s/%s" % (self.metadata.idk_dir(), self.log_file())

    def build_name(self):
        return "%s_%s_%s" % (self.metadata.driver_make,
                            self.metadata.driver_model,
                            self.metadata.driver_name)

    def archive_file(self):
        return "%s-%s-driver.zip" % (self.build_name(),
                                     self.metadata.version)

    def archive_path(self):
        return os.path.join(os.path.expanduser("~"),self.archive_file())


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

    def get_repackage_version(self, tag_base):
        """
        Get the driver version the user wants to repackage
        """
        # suggest the current driver version as default
        repkg_version = prompt.text( 'Driver Version to re-package', self.metadata.version )
        # confirm this version has the correct format
        self._verify_version(repkg_version)
        # check to make sure this driver version exists
        tag_name = tag_base + '_' + repkg_version.replace('.', '_')
        cmd = 'git tag -l ' + tag_name
        # find out if this tag name exists
        output = subprocess.check_output(cmd, shell=True)
        if len(output) > 0:
            # this tag exists, check it out
            os.system('git checkout tags/' + tag_name)
        else:
            log.error('No driver version %s found', tag_name)
            raise InvalidParameters('No driver version %s found', tag_name)

    def make_branch(self, name):
        """
        Make a new branch for this release and tag it with the same name so we
        can get back to it
        """
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
        # confirm this version has the correct format
        self._verify_version(new_version)
        if new_version != self.metadata.version:
            # search for the tag for this version, find out if it already exists
            cmd = 'git tag -l ' + self.build_name() + '_' + new_version.replace('.', '_')
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

    def package_driver(self):
        """
        @brief Store driver files in a zip package
        """
        log.info("-- Building driver package")
        self._store_package_files()

    def run(self):
        print "*** Starting Driver Packaging Process***"
        
        # store the original directory since we will be navigating away from it
        original_dir = os.getcwd()

        # first create a temporary clone of ooici to work with
        self.clone_repo()
        
        # get which dataset agent is selected from the current metadata, use
        # this to get metadata from the cloned repo
        tmp_metadata = Metadata()
        # read metadata from the cloned repo
        self.metadata = Metadata(tmp_metadata.driver_make,
                                 tmp_metadata.driver_model,
                                 tmp_metadata.driver_name,
                                 REPODIR + '/marine-integrations')
        
        if "--repackage" in sys.argv:
            self.get_repackage_version(self.build_name())
        else:
            new_version = self.update_version()
            branch_name = self.build_name() + '_' + new_version.replace('.', '_')
            self.make_branch(branch_name)

        if "--no-test" in sys.argv:
            f = open(self.log_path(), "w")
            f.write("Tests manually bypassed with --no-test option\n")
            f.close()
            self.package_driver()
        else:
            if(self.run_qualification_tests()):
                self.package_driver()
                
        if not "--no-push" in sys.argv and not "--repackage" in sys.argv:
            cmd = 'git push'
            output = subprocess.check_output(cmd, shell=True)
            if len(output) > 0:
                log.debug('git push returned: %s', output)

        # go back to the original directory
        os.chdir(original_dir)

        print "Package Created: " + self.archive_path()

    def zipfile(self):
        """
        @brief Return the ZipFile object.  Create the file if it isn't already open
        @retval ZipFile object
        """
        if(not self._zipfile):
            self._zipfile = zipfile.ZipFile(self.archive_path(), mode="w")

        return self._zipfile

    def zipfile_compression(self):
        """
        @brief What type of compression should we use for the package file.  If we have access to zlib, we will compress
        @retval Compression type
        """

        if(self._compression): return self._compression

        try:
            import zlib
            self._compression = zipfile.ZIP_DEFLATED
            log.info("Setting compression level to deflated")
        except:
            log.info("Setting compression level to store only")
            self._compression = zipfile.ZIP_STORED

    def manifest(self):
        """
        @brief Return the PackageManifest object.  Create it if it doesn't already exist
        @retval PackageManifest object
        """
        if(not self._manifest):
            self._manifest = PackageManifest(self.metadata)

        return self._manifest

    ###
    #   Private Methods
    ###
    def _store_package_files(self):
        """
        @brief Store all files in zip archive and add them to the manifest file
        """
        # make sure metadata is up to date
        self.metadata = Metadata(self.metadata.driver_make,
                                 self.metadata.driver_model,
                                 self.metadata.driver_name,
                                 REPODIR + '/marine-integrations')
        
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
        str_path = "%s/%s" % (self.generator.resource_dir(), self.string_file())
        if os.path.exists(str_path):
            self._add_file(str_path, 'resource', 'driver string file')
        
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

    def _add_file(self, source, destdir=None, description=None):
        """
        @brief Add a file to the zip package and store the file in the manifest.
        """
        filename = os.path.basename(source)
        dest = filename
        if(destdir):
            dest = "%s/%s" % (destdir, filename)

        log.debug("archive %s to %s" % (filename, dest))

        self.manifest().add_file(dest, description);
        self.zipfile().write(source, dest, self.zipfile_compression())
        
    def _verify_version(self, version = None):
        """
        Ensure we have a good version number and that it has not already been packaged and published
        """
        if version == None:
            version = self.metadata.version

        if not version:
            raise ValidationFailure("Driver version required in metadata")

        p = re.compile("^\d+\.\d+\.\d+$")
        if not p.findall("%s" % version):
            raise ValidationFailure("Version format incorrect '%s', should be x.x.x" % version)


if __name__ == '__main__':
    app = PackageDriver()
    app.run()
