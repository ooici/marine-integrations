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
        data_port = opts.data_port,
        command_port = opts.command_port,
        monitor = opts.monitor
    )
    app.run()

def parseArgs():
    parser = argparse.ArgumentParser(description='Run instrument.')
    parser.add_argument('-make', nargs="?", help='Driver make')
    parser.add_argument('-model', nargs="?", help='Driver model')
    parser.add_argument('-name', nargs="?", help='Driver name')
    parser.add_argument('-driver_class', nargs="?", help='Class name for instrument driver')
    parser.add_argument('-ip_address', nargs="?", help='Instrument (or device server) IP address')
    parser.add_argument('-data_port', nargs="?", help='Instrument (or device server) TCP data port')
    parser.add_argument('-command_port', nargs="?", help='Instrument (or device server) TCP command port')
    parser.add_argument('-m', '--monitor', help='Start a port monitor window (default is no monitor)', action='store_true')

    return parser.parse_args()


if __name__ == '__main__':
    run()
