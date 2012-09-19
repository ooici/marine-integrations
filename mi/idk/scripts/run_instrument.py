__author__ = 'David Everett'

import argparse

from mi.idk.run_instrument import RunInstrument

def run():
    opts = parseArgs()

    app = RunInstrument(
        make = opts.make, 
        model = opts.model, 
        name = opts.name, 
        driver_class = opts.driver_class,
        ip_address = opts.ip_address,
        port = opts.port
    )
    app.run()

def parseArgs():
    parser = argparse.ArgumentParser(description='Switch the current driver.')
    parser.add_argument('-make', nargs="?", help='driver make')
    parser.add_argument('-model', nargs="?", help='driver model')
    parser.add_argument('-name', nargs="?", help='driver name')
    parser.add_argument('-driver_class', nargs="?", help='class name for instrument driver')
    parser.add_argument('-ip_address', nargs="?", help='instrument (or device server) IP address')
    parser.add_argument('-port', nargs="?", help='instrument (or device server) TCP port')

    return parser.parse_args()


if __name__ == '__main__':
    run()
