__author__ = 'David Everett'

import argparse

from mi.idk.run_instrument import RunInstrument

def run():
    opts = parseArgs()

    app = RunInstrument(
        # DHE: commenting out until port_agent supports this again.
        #monitor = opts.monitor,
        monitor = False,
        subscriber = opts.subscriber
    )
    app.run()

def parseArgs():
    parser = argparse.ArgumentParser(description='Run instrument.')
    # DHE: commenting out until port_agent supports this again.
    #parser.add_argument('-m', '--monitor', help='Start a port monitor window (default is no monitor)', action='store_true')
    parser.add_argument('-s', '--subscriber', help='Start a data subscriber window (default is no subscriber)', action='store_true')

    return parser.parse_args()


if __name__ == '__main__':
    run()
