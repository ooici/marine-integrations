"""
@file coi-services/mi.idk.dataset/package_driver.py
@author Emily Hahn
@brief Main script class for running the package_driver process
"""

from mi.core.log import get_logger ; log = get_logger()

import mi.idk.package_driver

from mi.idk.dataset.metadata import Metadata
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
        log.info("In dsa package driver init")
        self.metadata = Metadata()
        self._zipfile = None
        self._manifest = None
        self._compression = None
        self.generator = DriverGenerator(self.metadata)

        # Set compression level
        self.zipfile_compression()
        
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




