"""
@file coi-services/mi.idk/switch_driver.py
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

    def fetch_comm_config(self):
        """
        @brief collect connection information for the logger from the user
        """
        config_path = "%s/%s" % (self.metadata.driver_dir(), CommConfig.config_filename())
        self.comm_config = CommConfig.get_config_from_console(config_path)
        self.comm_config.get_from_console()

    def run(self):
        """
        @brief Run it.
        """
        print( "*** Starting Switch Driver Process***" )

        self.fetch_metadata()

        if not exists(self.metadata.driver_dir()):
            raise DriverDoesNotExist( "%s/%s/$%s" % (self.metadata.driver_make,
                                                     self.metadata.driver_model,
                                                     self.driver_name))
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
        return ['master']

