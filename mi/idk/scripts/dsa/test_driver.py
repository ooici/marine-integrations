__author__ = 'Bill French'

import argparse

from mi.idk.dataset.nose_test import NoseTest
from mi.idk.nose_test import BUILDBOT_DRIVER_FILE
from mi.idk.dataset.metadata import Metadata
from mi.core.log import get_logger ; log = get_logger()

import yaml
import os
from mi.idk.config import Config
from mi.idk.nose_test import BuildBotConfig

BUILDBOT_DRIVER_FILE = "config/buildbot.yml"


def run():
    """
    Run tests for one or more drivers.  If -b is passed then
    we read driver list from the build bot configuration, otherwise
    we use the current IDK driver.
    @return: If any test fails return false, otherwise true
    """

    opts = parseArgs()
    failure = False

    for metadata in get_metadata(opts):
        app = NoseTest(metadata, testname=opts.testname, suppress_stdout=opts.suppress_stdout, noseargs=opts.noseargs)

        app.report_header()

        if( opts.unit ):
            success = app.run_unit()
        elif( opts.integration ):
            success = app.run_integration()
        elif( opts.qualification ):
            success = app.run_qualification()
        elif( opts.publication ):
            success = app.run_publication()
        else:
            success = app.run()

        if(not success): failure = True

    return failure

def get_metadata(opts):
    """
    return a list of metadata objects that we would like to
    run test for.  If buildbot option is set then we read
    from the config file, otherwise we return the current
    IDK driver metadata
    @param opts: command line options dictionary.
    @return: list of all metadata data objects we would
             like to run tests for.
    """
    result = []
    if(opts.buildbot):
        devices = read_buildbot_config()
        ret = True
        for (key, config) in devices:
            make = config.get(BuildBotConfig.MAKE)
            model = config.get(BuildBotConfig.MODEL)
            flavor =config.get(BuildBotConfig.FLAVOR)
            metadata = Metadata(make, model, flavor)
            result.append(metadata)
        pass
    else:
        result.append(Metadata())

    return result

def parseArgs():
    parser = argparse.ArgumentParser(description="IDK Start Driver")
    parser.add_argument("-s", dest='suppress_stdout', action="store_true",
                        help="hide stdout" )
    parser.add_argument("-u", dest='unit', action="store_true",
                        help="only run unit tests" )
    parser.add_argument("-i", dest='integration', action="store_true",
                        help="only run integration tests" )
    parser.add_argument("-q", dest='qualification', action="store_true",
                        help="only run qualification tests" )
    parser.add_argument("-p", dest='publication', action="store_true",
        help="only run publication tests" )
    parser.add_argument("-b", dest='buildbot', action="store_true",
        help="run all tests for drivers listed in %s" % BUILDBOT_DRIVER_FILE)
    parser.add_argument("-t", dest='testname',
                        help="test function name to run (all if not set)" )
    parser.add_argument("-n", dest='noseargs',
        help="extra nosetest args, use '+' for '-'" )
    #parser.add_argument("-m", dest='launch_monitor', action="store_true",
    #                    help="Launch data file monitor" )
    return parser.parse_args()

def read_buildbot_config():
    """
    Read the buildbot driver config and return a list of tuples with driver configs.
    We read the entire config file first so we can raise an exception before we run
    any tests.
    @return: list of tuples containing driver configs.
    @raise IDKConfigMissing if a driver config is missing a parameter
    """
    config_file = os.path.join(Config().base_dir(), BUILDBOT_DRIVER_FILE)
    drivers = yaml.load(file(config_file))

    log.error("Read drivers from %s" % config_file)
    log.error("Yaml load result: %s" % drivers)

    result = []

    # verify we have everything we need in the config
    for (key, config) in drivers.items():
        if(not config.get(BuildBotConfig.MAKE)
           or not config.get(BuildBotConfig.MODEL)
           or not config.get(BuildBotConfig.FLAVOR)):
            raise IDKConfigMissing("%s missing configuration" % key)

    return drivers.items()

if __name__ == '__main__':
    run()
