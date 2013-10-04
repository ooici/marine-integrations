"""
@file coi-services/mi/idk/dataset/switch_driver.py
@author Bill French
@brief Main script class for running the switch_driver process
"""

from os.path import exists, join, isdir
from os import listdir

from mi.idk.metadata import Metadata
from mi.idk.comm_config import CommConfig
from mi.idk.config import Config
from mi.idk.exceptions import DriverDoesNotExist

from mi.core.log import get_logger ; log = get_logger()

import os
import re
from glob import glob
import subprocess

from mi.idk import prompt
import mi.idk.switch_driver
import mi.idk.dataset.metadata

class SwitchDriver(mi.idk.switch_driver.SwitchDriver):
    """
    Main class for running the switch driver process.
    """

    def __init__(self, path=None, version=None):
        self.driver_path = path
        self.driver_version = version

    def fetch_metadata(self):
        """
        @brief collect metadata from the user
        """
        if not (self.driver_path):
            self.driver_path = prompt.text( 'Driver Path' )

        self.metadata = mi.idk.dataset.metadata.Metadata(self.driver_path)
        self.driver_version = prompt.text('Driver Version', self.metadata.version)

    def fetch_comm_config(self):
        """
        @brief No comm config for dsa
        """
        pass

    def checkout_version(self):
        """
        @brief Checkout the driver version from the repository
        """
        base_name = 'dsd_%s_%s' % (self.driver_path.replace('/', '_'),
                                   self.driver_version.replace('.', '_'))
        cmd = 'git tag -l ' + 'release_' + base_name
        output = subprocess.check_output(cmd, shell=True)
        if len(output) > 0:
            # this tag exists, check out the branch
            #(tag is the branch name with 'release_' in front)
            # checkout the branch so changes can be saved
            cmd = 'git checkout ' + base_name
            output = subprocess.check_output(cmd, shell=True)
            # re-read metadata file since it has changed
            self.metadata = mi.idk.dataset.metadata.Metadata(self.driver_path)
        else:
            raise DriverDoesNotExist("Driver version %s does not exist", self.driver_version)

    @staticmethod
    def list_drivers():
        """
        @brief Print a list of all the different drivers and their versions
        """
        drivers = SwitchDriver.get_drivers()

        for driver in sorted(drivers.keys()):
            for version in sorted(drivers[driver]):
                print "%s %s" % (driver, version)

    @staticmethod
    def get_drivers():
        """
        @brief Get a list of all the different drivers and their versions
        """
        result = {}
        driver_dir = join(Config().get("working_repo"), 'mi', 'dataset', 'driver')
        log.debug("Driver Dir: %s", driver_dir)

        files = []
        for dirname,_,_ in os.walk(driver_dir):
            files.extend(glob(os.path.join(dirname,"metadata.yml")))

        log.debug("Files: %s", files)

        for f in files:
            matcher = re.compile( "%s/(.*)/metadata.yml" % driver_dir )
            match = matcher.match(f)
            path = match.group(1)
            result[path] = SwitchDriver.get_versions(path)

        return result

    @staticmethod
    def get_versions(path):
        """
        @brief Get all versions for this driver from the tags
        @param path - the driver path 
        """
        # get all tags that start with this instrument
        cmd = 'git tag -l ' + 'release_dsd_' + path.replace('/', '_') + '*'
        output = subprocess.check_output(cmd, shell=True)
        version_list = []
        if len(output) > 0:
            tag_regex = re.compile(r'release_dsd_[a-z0-9_]+(\d+_\d+_\d+)')
            tag_iter = tag_regex.finditer(output)
            for tag_match in tag_iter:
                version_list.append(tag_match.group(1))
        return version_list

