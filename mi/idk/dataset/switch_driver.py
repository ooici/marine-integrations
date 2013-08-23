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

    def fetch_comm_config(self):
        """
        @brief No comm config for dsa
        """
        pass

    @staticmethod
    def list_drivers():
        drivers = SwitchDriver.get_drivers()

        for driver in sorted(drivers.keys()):
            for version in sorted(drivers[driver]):
                print "%s %s" % (driver, version)


    @staticmethod
    def get_drivers():
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
        return ['master']

