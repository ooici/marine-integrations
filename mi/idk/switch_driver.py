"""
@file coi-services/mi.idk/switch_driver.py
@author Bill French
@brief Main script class for running the switch_driver process
"""
import re
import subprocess

from os.path import exists, join, isdir
from os import listdir

from mi.idk.metadata import Metadata
from mi.idk.comm_config import CommConfig
from mi.idk.config import Config
from mi.idk.exceptions import DriverDoesNotExist

from mi.core.log import get_logger ; log = get_logger()

from mi.idk import prompt

class SwitchDriver():
    """
    Main class for running the switch driver process. 
    """

    def __init__(self, make=None, model=None, name=None, version=None):
        self.driver_make = make
        self.driver_model = model
        self.driver_name = name
        self.driver_version = version

    def fetch_metadata(self):
        """
        @brief collect metadata from the user
        """
        if not (self.driver_make and self.driver_model and self.driver_name):
            self.driver_make = prompt.text( 'Driver Make', self.driver_make )
            self.driver_model = prompt.text( 'Driver Model', self.driver_model )
            self.driver_name = prompt.text( 'Driver Name', self.driver_name )

        self.metadata = Metadata(self.driver_make, self.driver_model, self.driver_name)
        self.driver_version = prompt.text('Driver Version', self.metadata.version)

    def fetch_comm_config(self):
        """
        @brief collect connection information for the logger from the user
        """
        config_path = "%s/%s" % (self.metadata.driver_dir(), CommConfig.config_filename())
        self.comm_config = CommConfig.get_config_from_console(config_path)
        self.comm_config.get_from_console()

    def checkout_version(self):
        base_name = '%s_%s_%s_%s' % (self.driver_make,
                                            self.driver_model,
                                            self.driver_name,
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
            self.metadata = Metadata(self.driver_make, self.driver_model, self.driver_name)
        else:
            raise DriverDoesNotExist("Driver version %s does not exist", self.driver_version)

    def run(self):
        """
        @brief Run it.
        """
        print( "*** Starting Switch Driver Process***" )

        self.fetch_metadata()

        if not exists(self.metadata.driver_dir()):
            raise DriverDoesNotExist( "%s", self.metadata.driver_dir() )
        # if this version does not match the requested one, make sure the version exists,
        # then checkout the branch with that version
        if self.driver_version != self.metadata.version:
            self.checkout_version()
        self.fetch_comm_config()
        self.metadata.link_current_metadata()

    @staticmethod
    def list_drivers():
        driver_dir = join(Config().get("working_repo"), 'mi', 'instrument')
        log.debug("Driver Dir: %s", driver_dir)

        drivers = SwitchDriver.get_drivers()

        for make in sorted(drivers.keys()):
            for model in sorted(drivers[make].keys()):
                for name in sorted(drivers[make][model].keys()):
                    for version in sorted(drivers[make][model][name]):
                        print "%s %s %s %s" % (make, model, name, version)

    @staticmethod
    def get_drivers():
        driver_dir = join(Config().get("working_repo"), 'mi', 'instrument')
        log.debug("Driver Dir: %s", driver_dir)

        drivers = {}

        for make in listdir(driver_dir):
            make_dir = join(driver_dir, make)
            if isdir(make_dir) and not make == 'test':
                for model in listdir(make_dir):
                    model_dir = join(make_dir, model)
                    if isdir(model_dir) and not model == 'test':
                        for name in listdir(model_dir):
                            name_dir = join(model_dir, name)
                            if isdir(name_dir) and not name == 'test':
                                log.debug("found driver: %s %s %s", make, model, name)
                                if not drivers.get(make): drivers[make] = {}
                                if not drivers[make].get(model): drivers[make][model] = {}
                                drivers[make][model][name] = SwitchDriver.get_versions(make,model,name)

        return drivers

    @staticmethod
    def get_versions(make, model, name):
        full_name = 'release_%s_%s_%s' % (make, model, name)
        # get all tags that start with this instrument
        cmd = 'git tag -l ' + full_name + '*'
        output = subprocess.check_output(cmd, shell=True)
        version_list = []
        if len(output) > 0:
            tag_regex = re.compile(r'release_[a-z0-9_]+(\d+_\d+_\d+)')
            tag_iter = tag_regex.finditer(output)
            for tag_match in tag_iter:
                version_list.append(tag_match.group(1))
        return version_list

