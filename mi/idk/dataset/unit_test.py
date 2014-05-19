#! /usr/bin/env python

"""
@file coi-services/ion/idk/data_set_agent/unit_test.py
@author Bill French
@brief Base classes for data set agent tests.
"""
import os
import time
import gevent
import shutil
import hashlib

from mi.core.log import get_logger ; log = get_logger()

import unittest
import re
from pprint import PrettyPrinter

from mi.core.unit_test import MiIntTestCase
from mi.core.unit_test import ParticleTestMixin

from ooi.reflection import EggCache
from mi.idk.util import remove_all_files
from mi.idk.unit_test import InstrumentDriverTestConfig
from mi.idk.exceptions import TestNotInitialized
from mi.idk.exceptions import IDKConfigMissing
from mi.idk.exceptions import IDKException
from mi.idk.exceptions import SampleTimeout
from mi.core.exceptions import ConfigurationException
from mi.core.exceptions import InstrumentParameterException

from mi.dataset.dataset_driver import DriverParameter

from mi.idk.unit_test import AgentCapabilityType
from mi.idk.result_set import ResultSet
from mi.idk.dataset.metadata import Metadata
from mi.idk.instrument_agent_client import InstrumentAgentClient
from mi.idk.instrument_agent_client import InstrumentAgentDataSubscribers
from mi.idk.instrument_agent_client import InstrumentAgentEventSubscribers
from mi.dataset.dataset_driver import DataSourceConfigKey, DriverParameter
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.instrument_driver import DriverEvent

from interface.objects import ResourceAgentConnectionLostErrorEvent

from pyon.core.exception import Conflict
from pyon.core.exception import ResourceError, BadRequest, Timeout, ServerError
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

from interface.objects import AgentCommandResult
from interface.objects import AgentCommand
from interface.objects import AgentCapability
from interface.objects import CapabilityType

class DataSetTestConfig(InstrumentDriverTestConfig):
    """
    Singleton driver test config object.
    """
    agent_module = 'mi.idk.instrument_agent'
    agent_class = 'DatasetAgent'

    container_deploy_file = 'deploy/r2qual.yml'
    publisher_deploy_file = 'deploy/r2pub.yml'

    def initialize(self, *args, **kwargs):
        super(DataSetTestConfig, self).initialize(*args, **kwargs)

        log.debug("Dataset Agent Test Config:")
        for property, value in vars(self).iteritems():
            log.debug("key: %s, value: %s", property, value)

        log.debug("Dataset Agent Test Initialized")

    def initialize_ingester_test(self, directory, runtime):
        self.ingestion_directory = directory
        self.ingestion_runtime = runtime


class DataSetTestCase(MiIntTestCase):
    """
    Base class for instrument driver tests
    """
    # configuration singleton
    test_config = DataSetTestConfig()

    @classmethod
    def initialize(cls, *args, **kwargs):
        """
        Initialize the test_configuration singleton
        """
        cls.test_config.initialize(*args,**kwargs)

    def setUp(self):
        """
        @brief Setup test cases.
        """
        log.debug("*********************************************************************")
        log.debug("Starting Dataset Test %s", self._testMethodName)
        log.debug("*********************************************************************")
        log.debug("ID: %s", self.id())
        log.debug("DataSetTestCase setUp")

        # Test to ensure we have initialized our test config
        if not self.test_config.initialized:
            return TestNotInitialized(msg="Tests non initialized. Missing DataSetTestCase.initialize(...)?")

        log.debug("Driver Config: %s", self._driver_config())
        self._metadata = None

        self.clear_sample_data()

    def _driver_config(self):
        """
        Build the driver configuration and return it
        """
        config = {
            'dvr_mod' : self.test_config.driver_module,
            'dvr_cls' : self.test_config.driver_class,
            'startup_config' : self.test_config.driver_startup_config
        }
        return config

    def _agent_config(self):
        """
        Build the agent configuration and return it
        """
        config = {
            'driver_config': self._driver_config(),
            'stream_config' : self.data_subscribers.stream_config,
            'agent': {'resource_id': self.test_config.agent_resource_id}
        }
        return config

    def _get_metadata(self):
        """
        Get a metadata object for the test.  We will use the module name to try and determine the
        driver path.
        """
        if self._metadata is None:

            log.debug("Metadata self name: %s", self.__class__)

            regex = re.compile(r'.*mi.dataset\.driver\.(.*)\.test\.')
            match = regex.match(str(self.__class__))

            if match:
                driver_path = match.group(1)
                d = driver_path.replace(".", "/")
                log.debug("Driver path: %s", d)
                self._metadata = Metadata(d)
            else:
                self.fail(IDKException("Unable to determine driver path"))

        return self._metadata

    def _get_source_data_file(self, filename):
        """
        Search for a sample data file, first check the driver resource directory
        then just use the filename as a path.  If the file doesn't exists
        raise an exception
        @param filename name or path of the file to search for
        @return full path to the found data file
        @raise IDKException if the file isn't found
        """
        resource_dir = self._get_metadata().resource_dir()

        source_path = os.path.join(resource_dir, filename)

        log.debug("Search for resource file (%s) in %s", filename, resource_dir)
        if os.path.isfile(source_path):
            log.debug("Found %s in resource directory", filename)
            return source_path

        log.debug("Search for resource file (%s) in current directory", filename)
        if os.path.isfile(filename):
            log.debug("Found %s in the current directory", filename)
            return filename

        raise IDKException("Data file %s does not exist", filename)

    def create_data_dir(self):
        """
        Verify the test data directory is created and exists.  Return the path to
        the directory.
        @return: path to data directory
        @raise: IDKConfigMissing no harvester config
        @raise: IDKException if data_dir exists, but not a directory
        """
        startup_config = self._driver_config().get('startup_config')
        if not startup_config:
            raise IDKConfigMissing("Driver config missing 'startup_config'")

        harvester_config = startup_config.get(DataSourceConfigKey.HARVESTER)
        if not harvester_config:
            raise IDKConfigMissing("Startup config missing 'harvester' config")

        if DataSetDriverConfigKeys.DIRECTORY in harvester_config:
            # there is just one harvester config
            data_dir = harvester_config.get(DataSetDriverConfigKeys.DIRECTORY)
            if not data_dir:
                raise IDKConfigMissing("Harvester config missing 'directory'")

            if not os.path.exists(data_dir):
                log.debug("Creating data dir: %s", data_dir)
                os.makedirs(data_dir)

            elif not os.path.isdir(data_dir):
                raise IDKException("'data_dir' is not a directory")
        else:
            # return an array of dirs if there are multiple harvester configs
            data_dir = []
            for key in harvester_config:
                this_dir = harvester_config[key].get(DataSetDriverConfigKeys.DIRECTORY)
                if not this_dir:
                    raise IDKConfigMissing("Harvester config missing 'directory'")

                if not os.path.exists(this_dir):
                    log.debug("Creating data dir: %s", this_dir)
                    os.makedirs(this_dir)

                elif not os.path.isdir(this_dir):
                    raise IDKException("'data_dir' is not a directory")
                data_dir.append(this_dir)

        return data_dir
    
    def get_data_storage_dir(self):
        """
        Verify the test data directory is created and exists.  Return the path to
        the directory.
        @return: path to data directory
        @raise: IDKConfigMissing no harvester config
        @raise: IDKException if data_dir exists, but not a directory
        """
        startup_config = self._driver_config().get('startup_config')
        if not startup_config:
            raise IDKConfigMissing("Driver config missing 'startup_config'")

        harvester_config = startup_config.get(DataSourceConfigKey.HARVESTER)
        if not harvester_config:
            raise IDKConfigMissing("Startup config missing 'harvester' config")

        log.debug("Harvester config: %s", harvester_config)
        data_dir = harvester_config.get("storage_directory")

        log.debug("Data dir: %s", data_dir)

        return data_dir

    def remove_sample_dir(self):
        """
        Remove the sample dir and all files
        """
        data_dir = self.create_data_dir()
        self.clear_sample_data()
        if isinstance(data_dir, list):
            for d_dir in data_dir:
                os.rmdir(d_dir)
        else:
            os.rmdir(data_dir)

    def clear_sample_data(self):
        """
        Remove all files from the sample data directory
        """
        data_dir = self.create_data_dir()
        stored_data_dir = self.get_data_storage_dir()

        log.debug("Clean all data from %s", data_dir)
        if isinstance(data_dir, list):
            for d_dir in data_dir:
                remove_all_files(d_dir)
        else:
            remove_all_files(data_dir)

        # storage dir might not be in use
        log.debug("Clean all data from %s", stored_data_dir)
        if stored_data_dir:
            if isinstance(stored_data_dir, list):
                for d_dir in stored_data_dir:
                    if os.path.isdir(d_dir):
                        remove_all_files(d_dir)
            elif os.path.isdir(stored_data_dir):
                remove_all_files(stored_data_dir)

    def create_sample_data(self, filename, dest_filename=None, mode=0644, create=True):
        """
        Search for a data file in the driver resource directory and if the file
        is not found there then search using the filename directly.  Then copy
        the file to the test data directory.

        If a dest_filename is supplied it will be renamed in the destination
        directory.
        @param: filename - filename or path to a data file to copy
        @param: dest_filename - name of the file when copied. default to filename
        @param: file mode
        @param: create an empty file in the destination if the source is not found
        @return: path to file created
        """
        data_dir = self.create_data_dir()
        source_path = None

        try:
            source_path = self._get_source_data_file(filename)
        except IDKException as e:
            if not create:
                self.fail(e)

        log.debug("DIR: %s", data_dir)
        if dest_filename is None and source_path is not None:
            dest_path = os.path.join(data_dir, os.path.basename(source_path))
        elif dest_filename is None and source_path is None:
            dest_path = os.path.join(data_dir, filename)
        else:
            dest_path = os.path.join(data_dir, dest_filename)

        log.debug("Creating data file src: %s, dest: %s", source_path, dest_path)

        if source_path == None:
            file = open(dest_path, 'w')
            file.close()
        else:
            shutil.copy2(source_path, dest_path)

        os.chmod(dest_path, mode)

        return dest_path

    def create_sample_data_set_dir(self, filename, dest_dir, dest_filename=None, mode=0644, create=True):
        """
        Search for a data file in the driver resource directory and if the file
        is not found there then search using the filename directly.  Then copy
        the file to the test data directory.

        If a dest_filename is supplied it will be renamed in the destination
        directory.
        @param: filename - filename or path to a data file to copy
        @param: dest_filename - name of the file when copied. default to filename
        @param: file mode
        @param: create an empty file in the destination if the source is not found
        @return: path to file created
        """
        if not os.path.exists(dest_dir):
            log.debug("Creating data dir: %s", dest_dir)
            os.makedirs(dest_dir)

        elif not os.path.isdir(dest_dir):
            raise IDKException("'dest_dir' is not a directory")
        source_path = None

        try:
            source_path = self._get_source_data_file(filename)
        except IDKException as e:
            if not create:
                self.fail(e)

        log.debug("DIR: %s", dest_dir)
        if dest_filename is None and source_path is not None:
            dest_path = os.path.join(dest_dir, os.path.basename(source_path))
        elif dest_filename is None and source_path is None:
            dest_path = os.path.join(dest_dir, filename)
        else:
            dest_path = os.path.join(dest_dir, dest_filename)

        log.debug("Creating data file src: %s, dest: %s", source_path, dest_path)

        if source_path == None:
            file = open(dest_path, 'w')
            file.close()
        else:
            shutil.copy2(source_path, dest_path)

        os.chmod(dest_path, mode)

        return dest_path

    def get_file_state(self, path, ingested = False, position = None):
        """
        Create a state object for a file.  If a position is passed then add a parser state as well.
        """
        mod_time = os.path.getmtime(path)
        file_size = os.path.getsize(path)
        with open(path) as filehandle:
            md5_checksum = hashlib.md5(filehandle.read()).hexdigest()

        parser_state = {}
        if position:
            parser_state = {'position': position}

        return {
                   'ingested': ingested,
                   'file_mod_date': mod_time,
                   'file_checksum': md5_checksum,
                   'file_size': file_size,
                   'parser_state': parser_state
        }

class DataSetUnitTestCase(DataSetTestCase):
    """
    Base class for dataset driver unit tests
    """
    def setUp(self):
        super(DataSetUnitTestCase, self).setUp()


class DataSetIntegrationTestCase(DataSetTestCase):
    """
    Base class for dataset driver integration unit tests
    """
    def state_callback(self, state):
        log.debug("State callback: %s", state)
        self.state_callback_result.append(state)

    def data_callback(self, data):
        log.debug("Data callback: %s", data)
        if not isinstance(data, list):
            data = [data]
        for d in data:
            self.data_callback_result.append(d)

    def event_callback(self, **kwargs):
        log.debug("Event callback: %s", kwargs, exc_info=True)
        self.event_callback_result.append(kwargs)

    def exception_callback(self, ex):
        log.debug("Exception callback: %s", ex, exc_info=True)
        self.exception_callback_result.append(ex)

    def setUp(self):
        super(DataSetIntegrationTestCase, self).setUp()
        self.state_callback_result = []
        self.data_callback_result = []
        self.event_callback_result = []
        self.exception_callback_result = []

        self.memento = {}

        self.driver = self._get_driver_object()

        self.addCleanup(self._stop_driver)

    def _get_driver_object(self, **kwargs):
        config = kwargs.get('config', self._driver_config()['startup_config'])
        memento = kwargs.get('memento', self.memento)
        data_callback = kwargs.get('data_callback', self.data_callback)
        state_callback = kwargs.get('state_callback', self.state_callback)
        event_callback = kwargs.get('event_callback', self.event_callback)
        exception_callback = kwargs.get('exception_callback', self.exception_callback)

        module_object = __import__(self.test_config.driver_module, fromlist=[self.test_config.driver_class])
        class_object = getattr(module_object, self.test_config.driver_class)

        driver = class_object(config, memento, data_callback, state_callback, event_callback, exception_callback)
        return driver

    def _stop_driver(self):
        if self.driver:
            self.driver.shutdown()

    def clear_async_data(self):
        self.state_callback_result = []
        self.data_callback_result = []
        self.event_callback_result = []
        self.exception_callback_result = []

    def assert_exception(self, exception_class, timeout=35):
        """
        Wait for an exception in the exception callback queue
        """
        to = gevent.Timeout(timeout)
        to.start()
        done = False

        try:
            while not done:
                for exp in self.exception_callback_result:
                    if isinstance(exp, exception_class):
                        log.info("Expected exception detected: %s", exp)
                        done = True

                if not done:
                    log.debug("No exception detected yet, sleep for a bit")
                    gevent.sleep(1)

        except Timeout:
            log.error("Failed to detect exception %s", exception_class)
            self.fail("Exception detection failed.")

        finally:
            to.cancel()

    def assert_event(self, event_class_str, timeout=35):
        """
        Wait for an event in the event callback queue
        """
        to = gevent.Timeout(timeout)
        to.start()
        done = False

        try:
            while not done:
                for exp in self.event_callback_result:
                    if 'event_type' in exp and exp.get('event_type') == event_class_str:
                        log.info("Expected event detected: %s", exp)
                        done = True

                if not done:
                    log.debug("No event detected yet, sleep for a bit")
                    gevent.sleep(1)

        except Timeout:
            log.error("Failed to detect event %s", event_class_str)
            self.fail("Event detection failed.")

        finally:
            to.cancel()

    def assert_data(self, particle_class=None, result_set_file=None, count=1, timeout=10):
        """
        Wait for a data particle in the data callback queue
        @param particle_class, class of the expected data particles
        @param result_set_file, filename containing definition of the resulting dataset
        @param count, how many records to wait for
        @param timeout, how long to wait for the records.
        """
        try:
            particles = self.get_samples(particle_class, count, timeout)
        except Timeout:
            log.error("Failed to detect particle %s, expected %d particles, found %d", particle_class, count, found)
            self.fail("particle detection failed. Expected %d, Found %d" % (count, found))

        # Verify the data against the result data set definition
        if result_set_file:
            rs_file = self._get_source_data_file(result_set_file)
            rs = ResultSet(rs_file)

            self.assertTrue(rs.verify(particles), msg="Failed data validation, check the logs.")

    def assert_file_ingested(self, filename, data_source_key=None):
        """
        Assert that a particular file was ingested (useable by Single Directory driver, not Single File driver),
        If the ingested flag is not set in the driver state for this file, fail the test
        @ param filename name of the file to check that it was ingested using the ingested flag
        """
        log.debug("last state callback result %s", self.state_callback_result[-1])
        if data_source_key is None:
            last_state = self.state_callback_result[-1]
        else:
            last_state = self.state_callback_result[-1][data_source_key]
        if not filename in last_state or not last_state[filename]['ingested']:
            self.fail("File %s was not ingested" % filename)

    def assert_file_not_ingested(self, filename):
        """
        Assert that a particular file was not ingested (useable by Single Directory driver, not Single File driver),
        If the ingested flag is set in the driver state for this file, fail the test
        @ param filename name of the file to check that it was ingested using the ingested flag
        """
        log.debug("last state callback result %s", self.state_callback_result[-1])
        last_state = self.state_callback_result[-1]
        if filename in last_state and last_state[filename]['ingested']:
            self.fail("File %s was ingested when we expected it not to be" % filename)

    def get_samples(self, particle_class=None, count=1, timeout=10):
        """
        pop samples of the specified class from the data callback result queue
        @param particle_class None, a single particle class or a tuple of classes
        @param count the number of particles to return
        @param timeout how many seconds to wait for the specified number of particles
        """
        to = gevent.Timeout(timeout)
        to.start()
        result = []
        found = 0
        done = False

        try:
            while(not done):
                check_idx = 0
                # enumerate does not necessarily keep the particles in order as we remove other samples,
                # loop over data callback results starting with lowest index
                while len(self.data_callback_result) > 0 and found < count and \
                check_idx < len(self.data_callback_result):
                    data = self.data_callback_result[check_idx]
                    if particle_class is None or isinstance(data, particle_class):
                        found += 1
                        result.append(self.data_callback_result.pop(check_idx))
                        log.debug("Found sample index %d, #%d", check_idx, found)
                    else:
                        # skip past a particle that doesn't match our particle class
                        check_idx += 1

                    if found >= count:
                        log.debug("All done. %d >= %d", found, count)
                        done = True
                        break
                    # in case we have lots of callback results to check lets sleep
                    gevent.sleep(0)

                # data_callback_result may get updated while counting particles, check again
                if not done and self.data_callback_result == []:
                    log.debug("No particle detected yet, sleep for a bit")
                    gevent.sleep(1)
        except Timeout:
            log.error("Failed to detect particle %s, expected %d particles, found %d", particle_class, count, found)
            result = []
        finally:
            to.cancel()

        log.debug("Samples found: %d, %s", len(result), result)
        return result

###
#  Common integration tests
###

    def test_harvester_config_exception(self):
        """
        Start the a driver with a bad configuration.  Should raise
        an exception.
        """
        with self.assertRaises(ConfigurationException):
            self._get_driver_object(config={})

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        self.clear_sample_data()

        harvester_config = self._driver_config()['startup_config'][DataSourceConfigKey.HARVESTER]

        if DataSetDriverConfigKeys.PATTERN in harvester_config:
            pattern = harvester_config[DataSetDriverConfigKeys.PATTERN]
            filename = pattern.replace("*", "foo")
            self.assertIsNotNone(pattern)

            # create the file so that it is unreadable
            self.create_sample_data(filename, create=True, mode=000)

            # Start sampling and watch for an exception
            self.driver.start_sampling()

            self.assert_exception(IOError)
        else:
            # Start sampling and watch for an exceptions
            self.driver.start_sampling()

            # there are multiple harvester configs, test each one
            for key in harvester_config:
                pattern = harvester_config[key][DataSetDriverConfigKeys.PATTERN]
                filename = pattern.replace("*", "foo")
                file_dir = harvester_config[key][DataSetDriverConfigKeys.DIRECTORY]
                self.assertIsNotNone(pattern)
                self.assertIsNotNone(file_dir)

                # create the file so that it is unreadable
                self.create_sample_data_set_dir(filename, file_dir, create=True, mode=000)

                self.assert_exception(IOError)
                # clear out exceptions so we know we get a new one next key
                self.clear_async_data()

    def test_parameters(self):
        """
        Verify that we can get, set, and report all driver parameters.
        """
        expected_params = [DriverParameter.BATCHED_PARTICLE_COUNT,
                           DriverParameter.PUBLISHER_POLLING_INTERVAL,
                           DriverParameter.RECORDS_PER_SECOND]
        (res_cmds, res_params) = self.driver.get_resource_capabilities()

        # Ensure capabilities are as expected
        self.assertEqual(len(res_cmds), 1)
        self.assertEqual(len(res_params), len(expected_params))
        self.assertEqual(sorted(res_params), sorted(expected_params))

        # Verify default values are as expected.
        params = self.driver.get_resource(DriverParameter.ALL)
        log.debug("Get Resources Result: %s", params)
        self.assertEqual(params[DriverParameter.BATCHED_PARTICLE_COUNT], 1)
        self.assertEqual(params[DriverParameter.PUBLISHER_POLLING_INTERVAL], 1)
        self.assertEqual(params[DriverParameter.RECORDS_PER_SECOND], 60)

        # Try set resource individually
        self.driver.set_resource({DriverParameter.BATCHED_PARTICLE_COUNT: 2})
        self.driver.set_resource({DriverParameter.PUBLISHER_POLLING_INTERVAL: 2})
        self.driver.set_resource({DriverParameter.RECORDS_PER_SECOND: 59})

        params = self.driver.get_resource(DriverParameter.ALL)
        log.debug("Get Resources Result: %s", params)
        self.assertEqual(params[DriverParameter.BATCHED_PARTICLE_COUNT], 2)
        self.assertEqual(params[DriverParameter.PUBLISHER_POLLING_INTERVAL], 2)
        self.assertEqual(params[DriverParameter.RECORDS_PER_SECOND], 59)

        # Try set resource in bulk
        self.driver.set_resource(
            {DriverParameter.BATCHED_PARTICLE_COUNT: 1,
             DriverParameter.PUBLISHER_POLLING_INTERVAL: .1,
             DriverParameter.RECORDS_PER_SECOND: 60})

        params = self.driver.get_resource(DriverParameter.ALL)
        log.debug("Get Resources Result: %s", params)
        self.assertEqual(params[DriverParameter.BATCHED_PARTICLE_COUNT], 1)
        self.assertEqual(params[DriverParameter.PUBLISHER_POLLING_INTERVAL], .1)
        self.assertEqual(params[DriverParameter.RECORDS_PER_SECOND], 60)

        # Set with some bad values
        with self.assertRaises(InstrumentParameterException):
            self.driver.set_resource({DriverParameter.BATCHED_PARTICLE_COUNT: 'a'})
        with self.assertRaises(InstrumentParameterException):
            self.driver.set_resource({DriverParameter.BATCHED_PARTICLE_COUNT: -1})
        with self.assertRaises(InstrumentParameterException):
            self.driver.set_resource({DriverParameter.BATCHED_PARTICLE_COUNT: 0})

        # Try to configure with the driver startup config
        driver_config = self._driver_config()['startup_config']
        cfg = {
            DataSourceConfigKey.RESOURCE_ID: 'xxxxxxxx',
            DataSourceConfigKey.HARVESTER: driver_config.get(DataSourceConfigKey.HARVESTER),
            DataSourceConfigKey.PARSER: driver_config.get(DataSourceConfigKey.PARSER),
            DataSourceConfigKey.DRIVER: {
                DriverParameter.PUBLISHER_POLLING_INTERVAL: .2,
                DriverParameter.RECORDS_PER_SECOND: 3,
                DriverParameter.BATCHED_PARTICLE_COUNT: 3
            }
        }
        self.driver = self._get_driver_object(config=cfg)

        params = self.driver.get_resource(DriverParameter.ALL)
        log.debug("Get Resources Result: %s", params)
        self.assertEqual(params[DriverParameter.BATCHED_PARTICLE_COUNT], 3)
        self.assertEqual(params[DriverParameter.PUBLISHER_POLLING_INTERVAL], .2)
        self.assertEqual(params[DriverParameter.RECORDS_PER_SECOND], 3)

        # Finally verify we get a KeyError when sending in bad config keys
        cfg[DataSourceConfigKey.DRIVER] = {
            DriverParameter.PUBLISHER_POLLING_INTERVAL: .2,
            DriverParameter.RECORDS_PER_SECOND: 3,
            DriverParameter.BATCHED_PARTICLE_COUNT: 3,
            'something_extra': 1
        }

        with self.assertRaises(KeyError):
            self._get_driver_object(config=cfg)

    def test_schema(self):
        """
        Test the driver schema
        """
        config_json = self.driver.get_config_metadata()
        log.debug("config: %s", PrettyPrinter().pformat(config_json))

        ###
        # Driver
        ###
        driver = config_json.get('driver')
        self.assertEqual(driver, {})

        ###
        # Commands
        ###
        cmds = config_json.get('commands')
        self.assertIsNotNone(cmds)
        self.assertIsNotNone(cmds.get(DriverEvent.START_AUTOSAMPLE))
        self.assertIsNotNone(cmds.get(DriverEvent.STOP_AUTOSAMPLE))

        ###
        # Parameters
        ###
        params = config_json.get('parameters')
        self.assertIsNotNone(params)
        self.assertIsNotNone(params.get(DriverParameter.RECORDS_PER_SECOND))
        self.assertIsNotNone(params.get(DriverParameter.PUBLISHER_POLLING_INTERVAL))
        self.assertIsNotNone(params.get(DriverParameter.BATCHED_PARTICLE_COUNT))


class DataSetAgentTestCase(DataSetTestCase):
    """
    Base class for dataset driver unit tests
    """
    def setUp(self):
        """
        Startup the container and start the agent.
        """
        super(DataSetAgentTestCase, self).setUp()

        self.instrument_agent_manager = InstrumentAgentClient()
        self.instrument_agent_manager.start_container(deploy_file=self.test_config.container_deploy_file)

        self.container = self.instrument_agent_manager.container

        log.debug("Packet Config: %s", self.test_config.agent_packet_config)
        self.data_subscribers = InstrumentAgentDataSubscribers(
            packet_config=self.test_config.agent_packet_config,
            )
        self.event_subscribers = InstrumentAgentEventSubscribers(instrument_agent_resource_id=self.test_config.agent_resource_id)

        self.init_dataset_agent_client()

        self.event_subscribers.events_received = []
        self.data_subscribers.start_data_subscribers()

        log.debug("********* setUp complete.  Begin Testing *********")

        self.addCleanup(self._end_test)

    def _end_test(self):
        """
        Cleanup after the test completes or fails
        """
        log.debug("Starting test cleanup")
        #self.assert_reset()
        self.event_subscribers.stop()
        self.data_subscribers.stop_data_subscribers()
        self.instrument_agent_manager.stop_container()

        log.debug("Test complete and all cleaned up.")

    def init_dataset_agent_client(self, bootmode=None):
        self.set_dsa_client(self.get_dataset_agent_client(bootmode))
        log.debug("DSA Client.  Result: %s", self.dataset_agent_client)

    def get_dataset_agent_client(self, bootmode=None, config=None, resource_id=None, agent_name=None):
        log.info("Start Dataset Agent Client")

        if config is None:
            config = self._agent_config()

        if resource_id is None:
            resource_id = self.test_config.agent_resource_id

        if agent_name is None:
            agent_name = self.test_config.agent_name

        # Start instrument agent client.
        result = self.instrument_agent_manager.start_client(
            name=agent_name,
            module=self.test_config.agent_module,
            cls=self.test_config.agent_class,
            config=config,
            resource_id=resource_id,
            deploy_file=self.test_config.container_deploy_file,
            bootmode=bootmode
        )

        log.debug("DSA Initialized.  Result: %s", result)
        return self.instrument_agent_manager.instrument_agent_client

    def set_dsa_client(self, client):
        self.dataset_agent_client = client

    def get_dsa_client(self):
        return self.dataset_agent_client

    def stop_dataset_agent_client(self):
        log.debug("Stopping dataset agent. ff")
        self.instrument_agent_manager.stop_client()

    def get_samples(self, stream_name, sample_count = 1, timeout = 10):
        """
        listen on a stream until 'sample_count' samples are read and return
        a list of all samples read.  If the required number of samples aren't
        read then throw an exception.

        Note that this method does not clear the sample queue for the stream.
        This should be done explicitly by the caller.  However, samples that
        are consumed by this method are removed.

        @raise SampleTimeout - if the required number of samples aren't read
        """
        result = []
        start_time = time.time()
        i = 1

        log.debug("Fetch %d sample(s) from stream '%s'" % (sample_count, stream_name))
        while(len(result) < sample_count):
            if(self.data_subscribers.samples_received.has_key(stream_name) and
               len(self.data_subscribers.samples_received.get(stream_name))):
                log.trace("get_samples() received sample #%d!", i)
                result.append(self.data_subscribers.samples_received[stream_name].pop(0))
                log.debug('Popping received sample')
                i += 1

            # Check for timeout
            if(start_time + timeout < time.time()):
                raise SampleTimeout("DataSetQualificationTestCase.get_samples")

            if(not self.data_subscribers.samples_received.has_key(stream_name) or
               len(self.data_subscribers.samples_received.get(stream_name)) == 0):
                log.debug("No samples in queue, sleep for a bit")
                gevent.sleep(.2)

        log.debug("get_samples() complete.  returning %d records", sample_count)
        return result

    def assert_sample_queue_size(self, stream_name, size):
        """
        Verify that a queue has size samples in it.
        """
        if(not self.data_subscribers.samples_received.has_key(stream_name) and size == 0):
            return

        self.assertTrue(self.data_subscribers.samples_received.has_key(stream_name), msg="Sample queue does not exists")
        self.assertEqual(len(self.data_subscribers.samples_received.get(stream_name)), size)

    def assert_data_values(self, particles, dataset_definition_file):
        """
        Verify particles match the particles defined in the definition file
        """
        rs_file = self._get_source_data_file(dataset_definition_file)
        rs = ResultSet(rs_file)

        self.assertTrue(rs.verify(particles))

    def assert_initialize(self, final_state = ResourceAgentState.STREAMING):
        '''
        Walk through DSA states to get to streaming mode from uninitialized
        '''
        log.debug("Initialize DataSet agent, %s", self.dataset_agent_client)
        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.dataset_agent_client.execute_agent(cmd)
        state = self.dataset_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)
        log.info("Sent INITIALIZE; DSA state = %s", state)

        log.debug("DataSet agent go active")
        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.dataset_agent_client.execute_agent(cmd)
        state = self.dataset_agent_client.get_agent_state()
        log.info("Sent GO_ACTIVE; DSA state = %s", state)
        self.assertEqual(state, ResourceAgentState.IDLE)

        log.debug("DataSet agent run")
        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.dataset_agent_client.execute_agent(cmd)
        state = self.dataset_agent_client.get_agent_state()
        log.info("Sent RUN; DSA state = %s", state)
        self.assertEqual(state, ResourceAgentState.COMMAND)

        if final_state == ResourceAgentState.STREAMING:
            self.assert_start_sampling()

    def assert_stop_sampling(self):
        '''
        transition to command.  Must be called from streaming
        '''
        state = self.dataset_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)

        log.debug("DataSet agent stop sampling")
        cmd = AgentCommand(command=DriverEvent.STOP_AUTOSAMPLE)
        retval = self.dataset_agent_client.execute_resource(cmd)
        state = self.dataset_agent_client.get_agent_state()
        log.info("Sent STOP SAMPLING; DSA state = %s", state)
        self.assertEqual(state, ResourceAgentState.COMMAND)

    def assert_start_sampling(self):
        '''
        transition to sampling.  Must be called from command
        :rtype : object
        '''
        state = self.dataset_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        log.debug("DataSet agent start sampling")
        cmd = AgentCommand(command=DriverEvent.START_AUTOSAMPLE)
        retval = self.dataset_agent_client.execute_resource(cmd)
        state = self.dataset_agent_client.get_agent_state()
        log.info("Sent START SAMPLING; DSA state = %s", state)
        self.assertEqual(state, ResourceAgentState.STREAMING)

    def assert_reset(self):
        '''
        Put the instrument back in uninitialized
        '''
        agent_state = self.dataset_agent_client.get_agent_state()
        log.debug("Resetting agent: current state: %s", agent_state)

        if agent_state != ResourceAgentState.UNINITIALIZED:
            cmd = AgentCommand(command=ResourceAgentEvent.RESET)
            retval = self.dataset_agent_client.execute_agent(cmd)
            state = self.dataset_agent_client.get_agent_state()
            log.debug("Resetting agent: final state: %s", state)

    def assert_agent_state(self, target_state):
        """
        Verify the current agent state
        @param target_state: What we expect the agent state to be
        """
        state = self.dataset_agent_client.get_agent_state()
        self.assertEqual(state, target_state)

    def assert_agent_command(self, command, args=None, timeout=None, client=None):
        """
        Verify an agent command
        @param command: driver command to execute
        @param args: kwargs to pass to the agent command object
        """
        if client is None:
            client = self.dataset_agent_client

        cmd = AgentCommand(command=command, kwargs=args)
        retval = client.execute_agent(cmd, timeout=timeout)

    def assert_resource_command(self, command, args=None, timeout=None):
        """
        Verify a resource command
        @param command: driver command to execute
        @param args: kwargs to pass to the agent command object
        """
        cmd = AgentCommand(command=command, kwargs=args)
        retval = self.dataset_agent_client.execute_resource(cmd)

    def assert_state_change(self, target_agent_state, timeout=10):
        """
        Verify the agent and resource states change as expected within the timeout
        Fail if the state doesn't change to the expected state.
        @param target_agent_state: State we expect the agent to be in
        @param timeout: how long to wait for the driver to change states
        """
        to = gevent.Timeout(timeout)
        to.start()
        done = False
        agent_state = None

        try:
            while(not done):

                agent_state = self.dataset_agent_client.get_agent_state()
                log.error("Current agent state: %s", agent_state)

                if(agent_state == target_agent_state):
                    log.debug("Current state match: %s", agent_state)
                    done = True

                if not done:
                    log.debug("state mismatch, waiting for state to transition.")
                    gevent.sleep(1)
        except Timeout:
            log.error("Failed to transition agent state to %s, current state: %s", target_agent_state, agent_state)
            self.fail("Failed to transition state.")
        finally:
            to.cancel()

    def assert_event_received(self, event_object_type, timeout=10):
        """
        Verify an event has been received of a sepecific type
        @param event_object_type: Event object we are looking for
        @param timeout: how long to wait
        """
        to = gevent.Timeout(timeout)
        to.start()
        done = False

        try:
            while(not done):
                for event in self.event_subscribers.events_received:
                    log.debug("Event: %s", event)

                    if isinstance(event, event_object_type):
                        done = True

                if not done:
                    log.debug("target event not detected, sleep a bit to let events happen")
                    gevent.sleep(1)
        except Timeout:
            log.error("Failed to find event in queue: %s", event_object_type)
            log.error("Current event queue: %s", self.event_subscribers._events_received)
            self.fail("%s event not detected")
        finally:
            to.cancel()

        log.info("Expected event detected: %s", event)

class DataSetQualificationTestCase(DataSetAgentTestCase):
    """
    Base class for dataset driver unit tests
    """

    def test_initialize(self):
        """
        Test that we can start the container and initialize the dataset agent.
        """
        self.assert_initialize()
        self.assert_stop_sampling()
        self.assert_reset()

    def test_resource_parameters(self):
        """
        verify we can get a resource parameter lists and get/set parameters.
        """
        def sort_capabilities(caps_list):
            '''
            sort a return value into capability buckets.
            @retval agt_cmds, agt_pars, res_cmds, res_iface, res_pars
            '''
            agt_cmds = []
            agt_pars = []
            res_cmds = []
            res_iface = []
            res_pars = []

            if len(caps_list)>0 and isinstance(caps_list[0], AgentCapability):
                agt_cmds = [x.name for x in caps_list if x.cap_type==CapabilityType.AGT_CMD]
                agt_pars = [x.name for x in caps_list if x.cap_type==CapabilityType.AGT_PAR]
                res_cmds = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_CMD]
                #res_iface = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_IFACE]
                res_pars = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_PAR]

            elif len(caps_list)>0 and isinstance(caps_list[0], dict):
                agt_cmds = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.AGT_CMD]
                agt_pars = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.AGT_PAR]
                res_cmds = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.RES_CMD]
                #res_iface = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.RES_IFACE]
                res_pars = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.RES_PAR]

            agt_cmds.sort()
            agt_pars.sort()
            res_cmds.sort()
            res_iface.sort()
            res_pars.sort()

            return agt_cmds, agt_pars, res_cmds, res_iface, res_pars

        log.debug("Initialize the agent")
        expected_params = [DriverParameter.BATCHED_PARTICLE_COUNT,
                           DriverParameter.PUBLISHER_POLLING_INTERVAL,
                           DriverParameter.RECORDS_PER_SECOND]
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        log.debug("Call get capabilities")
        retval = self.dataset_agent_client.get_capabilities()
        log.debug("Capabilities: %s", retval)
        agt_cmds, agt_pars, res_cmds, res_iface, res_pars = sort_capabilities(retval)
        self.assertEqual(sorted(res_pars), sorted(expected_params))

        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 20})
        reply = self.dataset_agent_client.get_resource(DriverParameter.ALL)
        log.debug("Get Resource Result: %s", reply)


    def test_capabilities(self):
        """
        Verify capabilities throughout the agent lifecycle
        """
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.UNINITIALIZED),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: None,
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: None,
        }

        ###
        # DSA State INACTIVE
        ###

        log.debug("Initialize DataSet agent")
        self.assert_agent_command(ResourceAgentEvent.INITIALIZE)
        self.assert_state_change(ResourceAgentState.INACTIVE)
        self.assert_capabilities(capabilities)

        ###
        # DSA State IDLE
        ###

        log.debug("DataSet agent go active")
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.IDLE)
        self.assert_agent_command(ResourceAgentEvent.GO_ACTIVE)
        self.assert_state_change(ResourceAgentState.IDLE)
        self.assert_capabilities(capabilities)

        ###
        # DSA State COMMAND
        ###

        log.debug("DataSet agent run")
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.COMMAND)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [DriverEvent.START_AUTOSAMPLE]
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = self._common_resource_parameters()
        self.assert_agent_command(ResourceAgentEvent.RUN)
        self.assert_state_change(ResourceAgentState.COMMAND)
        self.assert_capabilities(capabilities)

        ###
        # DSA State STREAMING
        ###
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [DriverEvent.STOP_AUTOSAMPLE]
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = self._common_resource_parameters()
        self.assert_start_sampling()
        self.assert_capabilities(capabilities)

        ###
        # DSA State COMMAND Revisited
        ###

        log.debug("DataSet agent run")
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.COMMAND)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [DriverEvent.START_AUTOSAMPLE]
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = self._common_resource_parameters()
        self.assert_stop_sampling()
        self.assert_capabilities(capabilities)

        ###
        # DSA State INACTIVE
        ###

        log.debug("DataSet agent run")
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.INACTIVE)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = None
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = None
        self.assert_agent_command(ResourceAgentEvent.GO_INACTIVE)
        self.assert_state_change(ResourceAgentState.INACTIVE)
        self.assert_capabilities(capabilities)

        ###
        # DSA State LOST_CONNECTION
        ###
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.LOST_CONNECTION)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = None
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = None
        self.assert_agent_command(ResourceAgentEvent.RESET)
        self.assert_state_change(ResourceAgentState.UNINITIALIZED)

        self.remove_sample_dir()
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)

    def assert_capabilities(self, capabilities):
        '''
        Verify that all capabilities are available for a give state

        @todo: Currently resource interface not implemented because it requires
               a submodule update and some of the submodules are in release
               states.  So for now, no resource interfaces

        @param: dictionary of all the different capability types that are
        supposed to be there. i.e.
        {
          agent_command = ['DO_MY_COMMAND'],
          agent_parameter = ['foo'],
          resource_command = None,
          resource_interface = None,
          resource_parameter = None,
        }
        '''
        def sort_capabilities(caps_list):
            '''
            sort a return value into capability buckets.
            @retval agt_cmds, agt_pars, res_cmds, res_iface, res_pars
            '''
            agt_cmds = []
            agt_pars = []
            res_cmds = []
            res_iface = []
            res_pars = []

            if len(caps_list)>0 and isinstance(caps_list[0], AgentCapability):
                agt_cmds = [x.name for x in caps_list if x.cap_type==CapabilityType.AGT_CMD]
                agt_pars = [x.name for x in caps_list if x.cap_type==CapabilityType.AGT_PAR]
                res_cmds = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_CMD]
                #res_iface = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_IFACE]
                res_pars = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_PAR]

            elif len(caps_list)>0 and isinstance(caps_list[0], dict):
                agt_cmds = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.AGT_CMD]
                agt_pars = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.AGT_PAR]
                res_cmds = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.RES_CMD]
                #res_iface = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.RES_IFACE]
                res_pars = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.RES_PAR]

            agt_cmds.sort()
            agt_pars.sort()
            res_cmds.sort()
            res_iface.sort()
            res_pars.sort()

            return agt_cmds, agt_pars, res_cmds, res_iface, res_pars

        if(not capabilities.get(AgentCapabilityType.AGENT_COMMAND)):
            capabilities[AgentCapabilityType.AGENT_COMMAND] = []
        if(not capabilities.get(AgentCapabilityType.AGENT_PARAMETER)):
            capabilities[AgentCapabilityType.AGENT_PARAMETER] = []
        if(not capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)):
            capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        if(not capabilities.get(AgentCapabilityType.RESOURCE_INTERFACE)):
            capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        if(not capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)):
            capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []


        expected_agent_cmd = capabilities.get(AgentCapabilityType.AGENT_COMMAND)
        expected_agent_cmd.sort()
        expected_agent_param = self._common_agent_parameters()
        expected_agent_param.sort()
        expected_res_cmd = capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)
        expected_res_cmd.sort()
        expected_res_param = capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)
        expected_res_param.sort()
        expected_res_int = capabilities.get(AgentCapabilityType.RESOURCE_INTERFACE)
        expected_res_int.sort()

        # go get the active capabilities
        retval = self.dataset_agent_client.get_capabilities()
        agt_cmds, agt_pars, res_cmds, res_iface, res_pars = sort_capabilities(retval)
        log.debug("Get capabilities retval: %s", retval)

        log.debug("Agent Commands: %s ", str(agt_cmds))
        log.debug("Compared to: %s", expected_agent_cmd)
        log.debug("Agent Parameters: %s ", str(agt_pars))
        log.debug("Compared to: %s", expected_agent_param)
        log.debug("Resource Commands: %s ", str(res_cmds))
        log.debug("Compared to: %s", expected_res_cmd)
        log.debug("Resource Interface: %s ", str(res_iface))
        log.debug("Compared to: %s", expected_res_int)
        log.debug("Resource Parameter: %s ", str(res_pars))
        log.debug("Compared to: %s", expected_res_param)

        # Compare to what we are supposed to have
        self.assertEqual(expected_agent_cmd, agt_cmds)
        self.assertEqual(expected_agent_param, agt_pars)
        self.assertEqual(expected_res_cmd, res_cmds)
        self.assertEqual(expected_res_int, res_iface)
        self.assertEqual(expected_res_param, res_pars)

    def _common_resource_parameters(self):
        '''
        list of common resource parameters
        @return: list of resource parameters
        '''
        return [DriverParameter.BATCHED_PARTICLE_COUNT,
                DriverParameter.PUBLISHER_POLLING_INTERVAL,
                DriverParameter.RECORDS_PER_SECOND]

    def _common_agent_parameters(self):
        '''
        list of common agent parameters
        @return: list of agent parameters
        '''
        return ['aggstatus', 'alerts', 'driver_name', 'driver_pid', 'example', 'pubrate', 'streams']

    def _common_agent_commands(self, agent_state):
        '''
        list of common agent parameters for a agent state
        @return: list of agent parameters
        @raise: KeyError for undefined agent state
        '''
        capabilities = {
            ResourceAgentState.UNINITIALIZED: [
                ResourceAgentEvent.GO_ACTIVE,
                ResourceAgentEvent.RESET,
            ],
            ResourceAgentState.IDLE: [
                ResourceAgentEvent.GO_INACTIVE,
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.RUN,
            ],
            ResourceAgentState.COMMAND: [
                ResourceAgentEvent.CLEAR,
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.GO_INACTIVE,
                ResourceAgentEvent.PAUSE
            ],
            ResourceAgentState.STREAMING: [
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.GO_INACTIVE
            ],

            ResourceAgentState.LOST_CONNECTION: [
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.GO_INACTIVE
            ],

            ResourceAgentState.INACTIVE: [
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.GO_ACTIVE
            ]
        }

        return capabilities[agent_state]

    def test_missing_directory(self):
        """
        Test starting the driver when the data directory doesn't exists.  This
        should prevent the driver from going into streaming mode.  When the
        directory is created then we should be able to transition into streaming.
        """
        self.remove_sample_dir()
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)

        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.create_data_dir()

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        harvester_config = self._driver_config()['startup_config'][DataSourceConfigKey.HARVESTER]
        log.debug('Harvester config %s', harvester_config)
        if DataSetDriverConfigKeys.PATTERN in harvester_config:
            pattern = harvester_config[DataSetDriverConfigKeys.PATTERN]
            filename = pattern.replace("*", "foo")
            self.assert_new_file_exception(filename)
        else:
            for key in harvester_config:
                pattern = harvester_config[key][DataSetDriverConfigKeys.PATTERN]
                file_dir = harvester_config[key][DataSetDriverConfigKeys.DIRECTORY]
                filename = pattern.replace("*", "foo")

                self.assert_new_file_exception(filename, file_dir)
                # stop sampling so we can start again
                self.assert_stop_sampling()

                # stop and restart the agent so we can test the next key new file exception
                self.stop_dataset_agent_client()
                self.init_dataset_agent_client()

    def assert_new_file_exception(self, filename, directory=None):
        """
        Assert that an unreadable file creates an exception and loses connection,
        then making that file readable regains the connection
        @param filename filename of the file to create
        @param directory optional directory to create file in, default to None
        """
        self.clear_sample_data()
        if directory is None:
            self.create_sample_data(filename, mode=000)
        else:
            self.create_sample_data_set_dir(filename, directory, mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        if directory is None:
            self.create_sample_data(filename)
        else:
            self.create_sample_data_set_dir(filename, directory)

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

    def test_autosample_recover(self):
        """
        Verify that if we stop the agent without stopping sampling first then
        the next agent startup will restore to streaming.
        """
        # First verify the happy path.  We start sampling, stop then reset
        # On reinit state should still be command mode
        self.assert_initialize()
        self.assert_stop_sampling()

        log.debug("stop data set agent")
        self.stop_dataset_agent_client()

        log.debug("restart data set agent")
        self.init_dataset_agent_client(bootmode='restart')
        self.assert_state_change(ResourceAgentState.COMMAND, 10)

        # Now start sampling and then just reset the instrument agent.
        # When we reinitialize go_active should put us in streaming mode.
        self.assert_start_sampling()
        self.stop_dataset_agent_client()

        self.init_dataset_agent_client(bootmode='restart')
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

class DataSetIngestionTestCase(DataSetAgentTestCase):
    """
    Base class for dataset driver unit tests
    """
    def test_ingestion(self):
        """
        Test that will start a dataset agent and put it into streaming
        mode.  Then run continually and ingest files until we exceed our
        specified runtime.  No runtime means run perpetually.
        """
        directory = DataSetTestConfig().ingestion_directory
        runtime = DataSetTestConfig().ingestion_runtime

        sleeptime = 600
        to = None

        if runtime:
            sleeptime = int(runtime)
            to = gevent.Timeout(sleeptime)
            to.start()

        try:
            # Now start the agent up and just hang out.
            self.assert_initialize()

            while True:
                log.debug("In our event sleep loop.  just resting for a bit.")
                gevent.sleep(sleeptime)

        except Timeout:
            log.info("Finished ingestion test as runtime has been exceeded")

        finally:
            if runtime:
                to.cancel()
