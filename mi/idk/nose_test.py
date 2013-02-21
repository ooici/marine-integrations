"""
@file coi-services/mi.idk/nose_test.py
@author Bill French
@brief Helper class to invoke nose tests
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import os
import sys
import nose
import inspect

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum

from mi.idk.metadata import Metadata
from mi.idk.config import Config
from mi.idk.comm_config import CommConfig
from mi.idk.driver_generator import DriverGenerator

from mi.idk.exceptions import IDKConfigMissing
from mi.idk.exceptions import DriverNotStarted
from mi.idk.exceptions import CommConfigReadFail
from mi.idk.exceptions import IDKException

from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import InstrumentDriverPublicationTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase

BUILDBOT_DRIVER_FILE = "config/buildbot.yml"

class BuildBotConfig(BaseEnum):
    MAKE = 'make'
    MODEL = 'model'
    FLAVOR = 'flavor'

class IDKTestClasses(BaseEnum):
    """
    Define base classes for unit tests
    """
    UNIT = InstrumentDriverUnitTestCase
    INT  = InstrumentDriverIntegrationTestCase
    QUAL = InstrumentDriverQualificationTestCase
    PUB  = InstrumentDriverPublicationTestCase

class NoseTest(object):
    """
    Helper class to invoke nose tests for drivers.
    """

    ###
    #   Private Methods
    ###
    def __init__(self, metadata, testname = None, log_file = None, suppress_stdout = False, noseargs = None, launch_data_moniotor = False):
        """
        @brief Constructor
        @param metadata IDK Metadata object
        @param log_file File to store test results.  If none specified log to STDOUT
        @param supress_stdout do not use the -s option with nosetest
        @param noseargs extra arguments to sent to nose.
        """
        self._testname = testname

        #os.environ['NOSE_NOCAPTURE'] = ""
        log.debug("ENV: %s" % os.environ)

        repo_dir = Config().get("working_repo")
        if(not repo_dir):
            raise IDKConfigMissing()
        
        # Ion scripts need to be run from the base os the repo dir so it has access
        # to resources using relative pathing.  So we just do 
        os.chdir(repo_dir)
        
        if( log_file ):
            self.log_fh = open(log_file, "w")
        else:
            self.log_fh = sys.stdout
            
        self.test_runner = nose.core.TextTestRunner(stream=self.log_fh)

        if(metadata):
            self._init_test(metadata)

        self._noseargs = noseargs
        self._suppress_stdout = suppress_stdout

    def __del__(self):
        """
        @brief Destructor.  If stdout has been reassigned then we need to reset it back.  It appears the nose.core.TextTestRunner
        takes STDOUT from us which seems weird (a bug?)
        """
        sys.stdout = sys.__stdout__

    def _init_test(self, metadata):
        """
        initialize the test with driver metadata
        """
        self.metadata = metadata
        if(not self.metadata.driver_name):
            raise DriverNotStarted()

        config_path = "%s/%s" % (self.metadata.driver_dir(), CommConfig.config_filename())
        self.comm_config = CommConfig.get_config_from_file(config_path)
        if(not self.comm_config):
            raise CommConfigReadFail(msg=config_path)

        self._inspect_driver_module(self._driver_test_module())

    def _log(self, message):
        """
        @brief Log a test message either to stdout or a log file.
        @param message message to be outputted
        """
        self.log_fh.write(message + "\n")

    def _output_metadata(self):
        self._log( "Metadata =>\n\n" + self.metadata.serialize())

    def _output_comm_config(self):
        self._log( "Comm Config =>\n\n" + self.comm_config.serialize())

    def _driver_test_module(self):
        generator = DriverGenerator(self.metadata)
        return generator.test_modulename()

    def _data_test_module(self):
        generator = DriverGenerator(self.metadata)
        return generator.data_test_modulename()

    def _driver_test_filename(self):
        generator = DriverGenerator(self.metadata)
        return generator.driver_test_path()

    def _qualification_test_module(self):
        return self._driver_test_module()

    def _unit_test_class(self):
        return 'UnitFromIDK'

    def _int_test_class(self):
        return 'IntFromIDK'

    def _qual_test_class(self):
        return 'QualFromIDK'

    def _pub_test_class(self):
        return 'PubFromIDK'

    def _unit_test_module_param(self):
        '''
        Module name and test to run
        @return: module name and optional test as string
        '''
        result = "%s:%s" % (self._driver_test_filename(), self._unit_test_class)
        if(self._testname): result = "%s.%s" % (result, self._testname)
        return result

    def _int_test_module_param(self):
        '''
        Module name and test to run
        @return: module name and optional test as string
        '''
        result = "%s:%s" % (self._driver_test_filename(), self._int_test_class)
        if(self._testname): result = "%s.%s" % (result, self._testname)
        return result

    def _qual_test_module_param(self):
        '''
        Module name and test to run
        @return: module name and optional test as string
        '''
        result = "%s:%s" % (self._driver_test_filename(), self._qual_test_class)
        if(self._testname): result = "%s.%s" % (result, self._testname)
        return result

    def _pub_test_module_param(self):
        '''
        Module name and test to run
        @return: module name and optional test as string
        '''
        result = "%s:%s" % (self._driver_test_filename(), self._pub_test_class)
        if(self._testname): result = "%s.%s" % (result, self._testname)
        return result

    def _inspect_driver_module(self, test_module):
        '''
        Search the driver module for class definitions which are UNIT, INT, and QUAL tests.  We will import the module
        do a little introspection and set member variables for the three test types.
        @raises: ImportError - we can't load the test module
        @raises: IDKException - if all three test types aren't found
        '''
        self._unit_test_class = None
        self._int_test_class = None
        self._qual_test_class = None
        self._pub_test_class = None

        __import__(test_module)
        module = sys.modules.get(test_module)
        classes = inspect.getmembers(module, inspect.isclass)

        for name,clsobj in classes:
            clsstr = "<class '%s.%s'>" % (test_module, name)

            # We only want to inspect classes defined in the test module explicitly.  Ignore imported classes
            if(clsstr == str(clsobj)):
                if(issubclass(clsobj, IDKTestClasses.UNIT)):
                    self._unit_test_class = name
                if(issubclass(clsobj, IDKTestClasses.INT)):
                    self._int_test_class = name
                if(issubclass(clsobj, IDKTestClasses.QUAL)):
                    self._qual_test_class = name
                if(issubclass(clsobj, IDKTestClasses.PUB)):
                    self._pub_test_class = name

        if(not self._unit_test_class):
            raise IDKException("unit test class not found")

        if(not self._qual_test_class):
            raise IDKException("qual test class not found")

        if(not self._int_test_class):
            raise IDKException("int test class not found")

    ###
    #   Public Methods
    ###
    def run(self):
        """
        @brief Run all tests
        @retval False if any test has failed, True if all successful
        """
        if(not self.run_unit()):
            self._log( "\n\n!!!! ERROR: Unit Tests Failed !!!!")
            return False
        elif(not self.run_integration()):
            self._log( "\n\n!!!! ERROR: Integration Tests Failed !!!!")
            return False
        elif(not self.run_qualification()):
            self._log( "\n\n!!!! ERROR: Qualification Tests Failed !!!!")
            return False
        # Publication tests are only run when explicitly asked for
        #elif(not self.run_publication()):
        #    self._log( "\n\n!!!! ERROR: Publication Tests Failed !!!!")
        #    return False
        else:
            self._log( "\n\nAll tests have passed!")
            return True

    def report_header(self):
        """
        @brief Output report header containing system information.  i.e. metadata stored, comm config, etc.
        @param message message to be outputted
        """
        self._log( "****************************************" )
        self._log( "***   Starting Drive Test Process    ***" )
        self._log( "****************************************\n" )

        self._output_metadata()
        self._output_comm_config()

    def run_unit(self):
        """
        @brief Run unit tests for a driver
        """
        self._log("*** Starting Unit Tests ***")
        self._log(" ==> module: " + self._driver_test_module())
        module = "%s" % (self._driver_test_module())

        args=[sys.argv[0]]
        args += self._nose_stdout()
        args += self._extra_args()
        args += [self._unit_test_module_param()]

        self._run_nose(module, args)

    def run_integration(self):
        """
        @brief Run integration tests for a driver
        """
        self._log("*** Starting Integration Tests ***")
        self._log(" ==> module: " + self._driver_test_module())
        args=[ sys.argv[0], self._nose_stdout(), '-v', '-a', 'INT', self._int_test_module_param()]
        module = "%s" % (self._driver_test_module())

        self._run_nose(module, args)

    def run_qualification(self):
        """
        @brief Run qualification test for a driver
        """
        self._log("*** Starting Qualification Tests ***")
        self._log(" ==> module: " + self._qualification_test_module())
        args=[ sys.argv[0], self._nose_stdout(), '-v', '-a', 'QUAL', self._qual_test_module_param()]
        module = "%s" % (self._qualification_test_module())

        self._run_nose(module, args)

    def run_publication(self):
        """
        @brief Run publication test for a driver
        """
        self._log("*** Starting Publication Tests ***")

        self._log(" ==> module: " + self._data_test_module())
        if(self._pub_test_class == None):
            raise IDKException("Test module does not contain publication tests")

        self._log(" ==> class: " + self._pub_test_module_param())
        args=[ sys.argv[0]]
        args += self._nose_stdout()
        args += ['-v', '-a', 'PUB']
        args += [self._pub_test_module_param()]

        module = "%s" % (self._data_test_module())

        self._run_nose(module, args)

    def _nose_stdout(self):
        """
        Return '-s' if we want to output stdout
        @return: Nosetest option for if we want stdout or not
        """
        if(self._suppress_stdout):
            return []
        else:
            return ["-s"]

    def _extra_args(self):
        """
        Return a list of extra arguments we want to send to nose.  Not, thise currently splits a string on whitespace
        which will catch quoted strings as well.  Some day we may need to make this a little smarter and split
        like the shell would split a command line.
        @return: list of nose arguments.
        """
        result = []
        if(self._noseargs):
            for arg in self._noseargs.split():
                result.append(arg.replace("+", "-"))

        return result

    def _run_nose(self, module, args):
        log.debug("running nose tests with args: %s" % args)
        log.debug("ARGV: %s" % sys.argv)
        return nose.run(defaultTest=module, testRunner=self.test_runner, argv=args, exit=False)

