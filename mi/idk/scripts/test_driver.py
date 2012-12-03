__author__ = 'Bill French'

import argparse

from mi.idk.nose_test import NoseTest
from mi.idk.metadata import Metadata

def run():
    opts = parseArgs()
    app = NoseTest(Metadata(), testname=opts.testname)

    if( opts.unit ):
        app.report_header()
        app.run_unit()
    elif( opts.integration ):
        app.report_header()
        app.run_integration()
    elif( opts.qualification ):
        app.report_header()
        app.run_qualification()
    else:
        app.run()

def parseArgs():
    parser = argparse.ArgumentParser(description="IDK Start Driver")
    parser.add_argument("-u", dest='unit', action="store_true",
                        help="only run unit tests" )
    parser.add_argument("-i", dest='integration', action="store_true",
                        help="only run integration tests" )
    parser.add_argument("-q", dest='qualification', action="store_true",
        help="only run qualification tests" )
    parser.add_argument("-t", dest='testname',
                        help="test function name to run (all if not set)" )
    #parser.add_argument("-m", dest='launch_monitor', action="store_true",
    #                    help="Launch data file monitor" )
    return parser.parse_args()


if __name__ == '__main__':
    run()
