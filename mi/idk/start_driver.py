"""
@file coi-services/mi.idk/start_driver.py
@author Bill French
@brief Main script class for running the start_driver process
"""

from mi.idk.metadata import Metadata
from mi.idk.comm_config import CommConfig
from mi.idk.driver_generator import DriverGenerator
from mi.idk.comm_config import CommConfig

class StartDriver():
    """
    Main class for running the start driver process.
    """

    def fetch_metadata(self):
        """
        @brief collect metadata from the user
        """
        self.metadata = Metadata()
        self.metadata.get_from_console()

    def fetch_comm_config(self):
        """
        @brief collect connection information for the logger from the user
        """
        config_path = "%s/%s" % (self.metadata.driver_dir(), CommConfig.config_filename())
        self.comm_config = CommConfig.get_config_from_console(config_path)
        self.comm_config.get_from_console()

    def generate_code(self, force = False):
        """
        @brief generate the directory structure, code and tests for the new driver.
        """
        driver = DriverGenerator( self.metadata, force = force )
        driver.generate()

    def overwrite(self):
        """
        @brief Overwrite the current files with what is stored in the current metadata file.
        """
        self.metadata = Metadata()
        config_path = "%s/%s" % (self.metadata.driver_dir(), CommConfig.config_filename())
        self.comm_config = CommConfig.get_config_from_file(config_path)
        self.generate_code(force = True)

    def run(self):
        """
        @brief Run it.
        """
        print( "*** Starting Driver Creation Process***" )

        self.fetch_metadata()
        self.fetch_comm_config()
        self.generate_code()


if __name__ == '__main__':
    app = StartDriver()
    app.run()
