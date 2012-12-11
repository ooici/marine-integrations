__author__ = 'unwin'

from os.path import exists, join, isdir
from os import listdir

from mi.idk.metadata import Metadata
from mi.idk.comm_config import CommConfig
from mi.idk.config import Config
from mi.idk.exceptions import DriverDoesNotExist

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.driver_generator import DriverGenerator
from mi.idk.nose_test import NoseTest

import csv
CONFIG_FILE = "config/buildbot_list.csv"


class BuildbotRunner():
    """
    Main class for running driver tests for drivers listed in
    config/buildbot_list.csv
    """

    def run(self):
        """
        For each driver (make, model, name, version) in the CONFIG_FILE, run the full test suite
        """
        #@TODO perhaps this should be modified to specify UNIT/INT/QUAL per line.

        with open(CONFIG_FILE, 'rb') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=',')
            for row in csvreader:
                (driver_make, driver_model, driver_name, driver_version) = row
                self.metadata = Metadata(driver_make, driver_model, driver_name)
                self.fetch_comm_config()

                generator = DriverGenerator(self.metadata)
                test_module = generator.test_modulename()

                print "driver_make: " + driver_make
                print "driver_model: " + driver_model
                print "driver_name: " + driver_name
                print "driver_version: " + driver_version
                print "config_file_path: " + self.comm_config.config_file_path
                print "data_port: " + str(self.comm_config.data_port)
                print "command_port: " + str(self.comm_config.command_port)
                print "test_module: " + str(test_module)

                self.metadata = Metadata()
                test = NoseTest(self.metadata)

                test.run()



    def fetch_comm_config(self):
        config_path = "%s/%s" % (self.metadata.driver_dir(), CommConfig.config_filename())
        self.comm_config = CommConfig.get_config_from_console(config_path)
        self.metadata.link_current_metadata()

if __name__ == '__main__':
    test = BuildbotRunner()

    test.run()
