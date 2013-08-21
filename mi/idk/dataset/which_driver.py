"""
@file coi-services/mi.idk/which_driver.py
@author Bill French
@brief Main script class for running the which_driver process
"""

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.dataset.metadata import Metadata

class WhichDriver():
    """
    Main class for running the which driver process.
    """
    def fetch_metadata(self):
        """
        @brief collect metadata from the user
        """
        self.metadata = Metadata()

    def run(self):
        """
        @brief Run it.
        """
        self.fetch_metadata()
        if self.metadata.driver_path:
            print "%s" % (self.metadata.driver_path)



if __name__ == '__main__':
    app = WhichDriver()
    app.run()
