__author__ = 'Bill French'

import argparse

from mi.idk.switch_driver import SwitchDriver

def run():
    app = SwitchDriver()
    app.run()
   

if __name__ == '__main__':
    run()
