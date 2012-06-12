"""
@file coi-services/mi.idk/driver_generator.py
@author Bill French
@brief Main script class for running the reinitializing 
       the IDK environment 
"""

from mi.idk.config import Config
from mi.core.log import log

class IDKRebase():
    """
    Main class for running the rebase process.
    """

    def run(self):
        """
        @brief Run it.
        """
        log.info( "*** IDK Rebase Process***" )
        Config().rebase()

if __name__ == '__main__':
    app = IDKRebase()
    app.run()
