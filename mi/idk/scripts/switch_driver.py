__author__ = 'Bill French'

import argparse

from mi.idk.switch_driver import SwitchDriver

def run():
    opts = parseArgs()

    if opts.list:
        SwitchDriver.list_drivers()
    else:
        app = SwitchDriver(make=opts.make, model=opts.model, name=opts.name, version=opts.version)
        app.run()

def parseArgs():
    parser = argparse.ArgumentParser(description='Switch the current driver.')
    parser.add_argument('make', nargs="?", help='driver make')
    parser.add_argument('model', nargs="?", help='driver model')
    parser.add_argument('name', nargs="?", help='driver name')
    parser.add_argument('version', nargs="?", help='driver version')
    parser.add_argument('--list', dest="list", action="store_true", help='list drivers')

    return parser.parse_args()


if __name__ == '__main__':
    run()
