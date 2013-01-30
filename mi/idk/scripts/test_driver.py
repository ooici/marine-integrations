__author__ = 'Bill French'

import argparse

from mi.idk.nose_test import NoseTest
from mi.idk.nose_test import BUILDBOT_DRIVER_FILE
from mi.idk.metadata import Metadata
from mi.core.log import get_logger ; log = get_logger()

import yaml
import os
from mi.idk.config import Config
from mi.idk.nose_test import BuildBotConfig

BUILDBOT_DRIVER_FILE = "config/buildbot.yml"


def run():

    opts = parseArgs()

    if( opts.buildbot_unit ):
        return not run_buildbot_unit(opts)

    if( opts.buildbot_int ):
        return not run_buildbot_int(opts)

    if( opts.buildbot_qual ):
        return not run_buildbot_qual(opts)

    if( opts.buildbot ):
        devices = read_buildbot_config()
        ret = True
        for (key, config) in devices:
            make = config.get(BuildBotConfig.MAKE)
            model = config.get(BuildBotConfig.MODEL)
            flavor =config.get(BuildBotConfig.FLAVOR)
            metadata = Metadata(make, model, flavor)
            app = NoseTest(metadata, testname=opts.testname)
            app.report_header()
            if False == app.run_unit():
                ret = False
            if False == app.run_integration():
                ret = False
            if False == app.run_qualification():
                ret = False
        return not ret

    else:
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

def run_buildbot_unit(opts):
    devices = read_buildbot_config()
    ret = True
    for (key, config) in devices:
        make = config.get(BuildBotConfig.MAKE)
        model = config.get(BuildBotConfig.MODEL)
        flavor =config.get(BuildBotConfig.FLAVOR)
        metadata = Metadata(make, model, flavor)
        app = NoseTest(metadata, testname=opts.testname)
        app.report_header()

        if False == app.run_unit():
            ret = False
    return ret

def run_buildbot_int(opts):
    devices = read_buildbot_config()
    ret = True
    for (key, config) in devices:
        make = config.get(BuildBotConfig.MAKE)
        model = config.get(BuildBotConfig.MODEL)
        flavor =config.get(BuildBotConfig.FLAVOR)
        metadata = Metadata(make, model, flavor)
        app = NoseTest(metadata, testname=opts.testname)
        app.report_header()

        if False == app.run_integration():
            ret = False
    return ret

def run_buildbot_qual(opts):
    devices = read_buildbot_config()
    ret = True
    for (key, config) in devices:
        make = config.get(BuildBotConfig.MAKE)
        model = config.get(BuildBotConfig.MODEL)
        flavor =config.get(BuildBotConfig.FLAVOR)
        metadata = Metadata(make, model, flavor)
        app = NoseTest(metadata, testname=opts.testname)
        app.report_header()

        if False == app.run_qualification():
            ret = False
    return ret

def parseArgs():
    parser = argparse.ArgumentParser(description="IDK Start Driver")
    parser.add_argument("-u", dest='unit', action="store_true",
                        help="only run unit tests" )
    parser.add_argument("-i", dest='integration', action="store_true",
                        help="only run integration tests" )
    parser.add_argument("-q", dest='qualification', action="store_true",
        help="only run qualification tests" )
    
    parser.add_argument("-bu", dest='buildbot_unit', action="store_true",
        help="run unit tests for drivers listed in %s" % BUILDBOT_DRIVER_FILE)
    parser.add_argument("-bi", dest='buildbot_int', action="store_true",
        help="run int tests for drivers listed in %s" % BUILDBOT_DRIVER_FILE)
    parser.add_argument("-bq", dest='buildbot_qual', action="store_true",
        help="run qual tests for drivers listed in %s" % BUILDBOT_DRIVER_FILE)

    parser.add_argument("-b", dest='buildbot', action="store_true",
        help="run all tests for drivers listed in %s" % BUILDBOT_DRIVER_FILE)
    parser.add_argument("-t", dest='testname',
        help="test function name to run (all if not set)" )
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
