__author__ = 'Bill French'

import argparse

from mi.idk.dataset.nose_test import NoseTest
from mi.idk.dataset.metadata import Metadata
from mi.core.log import get_logger ; log = get_logger()

import yaml
import time
import os
import re
from glob import glob
from mi.idk.config import Config

DEFAULT_DIR='/tmp/dsa_ingest'
EXCLUDED_DRIVERS = ['antelope/orb']

def run():
    """
    Run tests for one or more dataset drivers.  If -b is passed then
    we build all drivers, otherwise we use the current IDK driver.
    @return: If any test fails return false, otherwise true
    """

    opts = parseArgs()
    failed = False
    count = 0
    success = 0
    failure = 0
    error = 0
    start_time = time.time()

    for metadata in get_metadata(opts):
        count += 1
        app = NoseTest(metadata,
                       testname=opts.testname,
                       suppress_stdout=opts.suppress_stdout,
                       noseargs=opts.noseargs)

        app.report_header()

        if( opts.unit ):
            result = app.run_unit()
        elif( opts.integration ):
            result = app.run_integration()
        elif( opts.qualification ):
            result = app.run_qualification()
        elif( opts.ingest ):
            result = app.run_ingestion(opts.directory, opts.exit_time)
        else:
            result = app.run()

        if(not result): failed = True

        success += app.success_count
        error += app.error_count
        failure += app.failure_count

    if(count > 1):
        driver_report(count, time.time() - start_time, success, error, failure)

    return failure

def get_metadata(opts):
    """
    return a list of metadata objects that we would like to
    run test for.  If buildall option is set then we search
    the working directory tree for drivers, otherwise we
    return the current IDK driver metadata
    @param opts: command line options dictionary.
    @return: list of all metadata data objects we would
             like to run tests for.
    """
    result = []
    if(opts.buildall):
        paths = get_driver_paths()
        for path in paths:
            # Some drivers can't be run in batch tests
            if path not in EXCLUDED_DRIVERS:
                log.debug("Adding driver path: %s", path)
                result.append(Metadata(path))
    else:
        result.append(Metadata())

    return result

def parseArgs():
    parser = argparse.ArgumentParser(description="IDK Start Driver")
    parser.add_argument("-s", dest='suppress_stdout', action="store_true",
                        help="hide stdout" )
    parser.add_argument("-g", dest='ingest', action="store_true",
                        help="run ingestion test from directory" )
    parser.add_argument("-d", dest='directory',
                        help="ingestion directory for -g (DEFAULT: %s)" % DEFAULT_DIR,
                        default=DEFAULT_DIR)
    parser.add_argument("-x", dest='exit_time',
                        help="ingestion runtime in seconds for -g (DEFAULT: None)")
    parser.add_argument("-u", dest='unit', action="store_true",
                        help="only run unit tests" )
    parser.add_argument("-i", dest='integration', action="store_true",
                        help="only run integration tests" )
    parser.add_argument("-q", dest='qualification', action="store_true",
                        help="only run qualification tests" )
    parser.add_argument("-b", dest='buildall', action="store_true",
                        help="run all tests for all drivers")
    parser.add_argument("-t", dest='testname',
                        help="test function name to run (all if not set)" )
    parser.add_argument("-n", dest='noseargs',
                        help="extra nosetest args, use '+' for '-'" )
    #parser.add_argument("-m", dest='launch_monitor', action="store_true",
    #                    help="Launch data file monitor" )
    return parser.parse_args()

def get_driver_paths():
    """
    @brief Get a list of all the different dataset driver paths in the working
    directory
    """
    result = []
    driver_dir = os.path.join(Config().get("working_repo"), 'mi', 'dataset', 'driver')
    log.debug("Driver Dir: %s", driver_dir)

    files = []
    for dirname,_,_ in os.walk(driver_dir):
        files.extend(glob(os.path.join(dirname,"metadata.yml")))

    log.debug("Files: %s", files)

    for f in files:
        matcher = re.compile( "%s/(.*)/metadata.yml" % driver_dir )
        match = matcher.match(f)
        result.append(match.group(1))

    return result

if __name__ == '__main__':
    run()

def driver_report(count, duration, success, error, failure):
    msg ="\n------------------------ Cumulative Nosetest Result ------------------------\n"
    msg += "Drivers tested: %d\n" % count
    msg += "Ran %d tests in %.3fs\n\n" % (success + error + failure, duration)
    if(failure or error):
        msg += "FAILED ("
        if(error):
            msg += "errors=%d" % error
            if(failure): msg += ", "
        if(failure):
            msg += "failure=%d" % failure
        msg += ")"
    else:
        msg += "OK"
    msg += "\n"

    log.warn(msg)

