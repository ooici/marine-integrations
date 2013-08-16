"""
@file coi-services/mi/idk/dataset/start_driver.py
@author Bill French
@brief Main script class for running the start_driver process
"""

from mi.idk.dataset.metadata import Metadata
import mi.idk.dataset.driver_generator

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
        pass

    def generate_code(self, force = False):
        """
        @brief generate the directory structure, code and tests for the new driver.
        """
        driver = mi.idk.dataset.driver_generator.DriverGenerator( self.metadata, force = force)
        driver.generate()

    def overwrite(self):
        """
        @brief Overwrite the current files with what is stored in the current metadata file.
        """
        self.metadata = Metadata()
        self.generate_code(force = True)

    def run(self):
        """
        @brief Run it.
        """
        print( "*** Starting Driver Creation Process***" )

        self.fetch_metadata()
        self.generate_code()


if __name__ == '__main__':
    app = StartDriver()
    app.run()
