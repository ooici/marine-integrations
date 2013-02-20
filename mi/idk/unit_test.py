#! /usr/bin/env python

"""
@file coi-services/ion/idk/unit_test.py
@author Bill French
@brief Base classes for instrument driver tests.
"""

from mock import patch
from pyon.core.bootstrap import CFG

import re
import os
import time
import ntplib
import unittest
import datetime
from sets import Set

# Set testing to false because the capability container tries to clear out
# couchdb if we are testing. Since we don't care about couchdb for the most
# part we can ignore this. See initialize_ion_int_tests() for implementation.
# If you DO care about couch content make sure you do a force_clean when needed.
from pyon.core import bootstrap
bootstrap.testing = False

# Import pyon first for monkey patching.
from mi.core.log import get_logger ; log = get_logger()

import gevent
import json
import ntplib
import time

from mock import Mock
from mi.core.unit_test import MiIntTestCase
from mi.core.unit_test import MiUnitTest
from mi.core.port_agent_simulator import TCPSimulatorServer
from mi.core.instrument.instrument_driver import InstrumentDriver
from mi.core.instrument.instrument_protocol import InstrumentProtocol
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from ion.agents.port.port_agent_process import PortAgentProcessType
from interface.objects import AgentCapability
from interface.objects import CapabilityType

from ion.agents.instrument.driver_process import DriverProcess, DriverProcessType

from interface.objects import AgentCommand

from mi.idk.util import convert_enum_to_dict
from mi.idk.comm_config import CommConfig
from mi.idk.config import Config
from mi.idk.common import Singleton
from mi.idk.instrument_agent_client import InstrumentAgentClient
from mi.idk.instrument_agent_client import InstrumentAgentDataSubscribers
from mi.idk.instrument_agent_client import InstrumentAgentEventSubscribers

from mi.idk.exceptions import IDKException
from mi.idk.exceptions import TestNotInitialized
from mi.idk.exceptions import TestNoCommConfig

from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.port_agent_client import PortAgentClient
from mi.core.instrument.port_agent_client import PortAgentPacket
from mi.core.instrument.data_particle import CommonDataParticleType
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import DataParticleValue
from mi.core.instrument.data_particle import RawDataParticleKey
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.tcp_client import TcpClient
from mi.core.common import BaseEnum
from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
from ion.agents.port.port_agent_process import PortAgentProcess

from pyon.core.exception import Conflict
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

# Do not remove this import.  It is for package building.
from mi.core.instrument.zmq_driver_process import ZmqDriverProcess

GO_ACTIVE_TIMEOUT=180
GET_TIMEOUT=30
SET_TIMEOUT=90
EXECUTE_TIMEOUT=30
SAMPLE_RAW_DATA="Iam Apublished Message"

class DriverStartupConfigKey(BaseEnum):
    PARAMETERS = 'parameters'
    SCHEDULER = 'scheduler'

class AgentCapabilityType(BaseEnum):
    AGENT_COMMAND = 'agent_command'
    AGENT_PARAMETER = 'agent_parameter'
    RESOURCE_COMMAND = 'resource_command'
    RESOURCE_INTERFACE = 'resource_interface'
    RESOURCE_PARAMETER = 'resource_parameter'

class ParameterTestConfigKey(BaseEnum):
    """
    Defines the dict keys used in the data particle parameter config used in unit tests of data particles
    """
    TYPE = 'type'
    REQUIRED = 'required'
    NAME = 'name'
    VALUE = 'value'
    DIRECT_ACCESS = 'directaccess'
    STARTUP = 'startup'
    READONLY = 'readonly'
    DEFAULT = 'default'

class InstrumentDriverTestConfig(Singleton):
    """
    Singleton driver test config object.
    """
    driver_module  = None
    driver_class   = None

    working_dir    = "/tmp/" # requires trailing / or it messes up the path. should fix.

    delimeter      = ['<<','>>']
    logger_timeout = 15

    driver_process_type = DriverProcessType.PYTHON_MODULE
    instrument_agent_resource_id = None
    instrument_agent_name = None
    instrument_agent_module = 'mi.idk.instrument_agent'
    instrument_agent_class = 'InstrumentAgent'
    data_instrument_agent_module = 'mi.idk.instrument_agent'
    data_instrument_agent_class = 'PublisherInstrumentAgent'
    instrument_agent_packet_config = None
    instrument_agent_stream_encoding = 'ION R2'
    instrument_agent_stream_definition = None

    driver_startup_config = {}

    container_deploy_file = 'res/deploy/r2deploy.yml'
    publisher_deploy_file = 'res/deploy/r2idk.yml'

    initialized   = False

    def initialize(self, *args, **kwargs):
        self.driver_module = kwargs.get('driver_module')
        self.driver_class  = kwargs.get('driver_class')
        if kwargs.get('working_dir'):
            self.working_dir = kwargs.get('working_dir')
        if kwargs.get('delimeter'):
            self.delimeter = kwargs.get('delimeter')

        self.instrument_agent_preload_id = kwargs.get('instrument_agent_preload_id')
        self.instrument_agent_resource_id = kwargs.get('instrument_agent_resource_id')
        self.instrument_agent_name = kwargs.get('instrument_agent_name')
        self.instrument_agent_packet_config = self._build_packet_config(kwargs.get('instrument_agent_packet_config'))
        self.instrument_agent_stream_definition = kwargs.get('instrument_agent_stream_definition')
        if kwargs.get('instrument_agent_module'):
            self.instrument_agent_module = kwargs.get('instrument_agent_module')
        if kwargs.get('instrument_agent_class'):
            self.instrument_agent_class = kwargs.get('instrument_agent_class')
        if kwargs.get('instrument_agent_stream_encoding'):
            self.instrument_agent_stream_encoding = kwargs.get('instrument_agent_stream_encoding')

        if kwargs.get('container_deploy_file'):
            self.container_deploy_file = kwargs.get('container_deploy_file')

        if kwargs.get('logger_timeout'):
            self.container_deploy_file = kwargs.get('logger_timeout')

        if kwargs.get('driver_process_type'):
            self.container_deploy_file = kwargs.get('driver_process_type')

        if kwargs.get('driver_startup_config'):
            self.driver_startup_config = kwargs.get('driver_startup_config')

        self.initialized = True

    def _build_packet_config(self, param_config):
        """
        Build a packet config from various data types.
        @param packet_config: packet config object. Can be enum, dict or list
        @return list of stream names to create
        """
        params = []
        if(isinstance(param_config, list)):
            params = param_config

        elif(isinstance(param_config, BaseEnum)):
            params = param_config.list()

        elif(isinstance(param_config, dict)):
            params = [ value for (key, value) in param_config.items() ]

        else:
            log.error("Unknown param_config type")
            return []

        result = []
        for i in params:
            if(isinstance(i, tuple)):
                log.debug("BLAMMM")
                result.append(i[0])
            else:
                result.append(i)

        return result


class DriverTestMixin(MiUnitTest):
    """
    Base class for data particle mixin.  Used for data particle validation.
    """
    _raw_sample_parameters = {
        RawDataParticleKey.PAYLOAD: {'type': unicode, 'value': u'SWFtIEFwdWJsaXNoZWQgTWVzc2FnZQ=='},
        RawDataParticleKey.LENGTH: {'type': int, 'value': 22},
        RawDataParticleKey.TYPE: {'type': int, 'value': 2},
        RawDataParticleKey.CHECKSUM: {'type': int, 'value': 2757}
    }

    def assert_particle_raw(self, data_particle, verify_values = False):
        '''
        Verify a raw data particles
        @param data_particle:  SBE26plusTideSampleDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, CommonDataParticleType.RAW)
        self.assert_data_particle_parameters(data_particle, self._raw_sample_parameters, verify_values)

    def convert_data_particle_to_dict(self, data_particle):
        """
        Convert a data particle object to a dict.  This will work for data particles as
        DataParticle object, dictionaries or a string
        @param data_particle: data particle
        @return: dictionary representation of a data particle
        """
        if (isinstance(data_particle, DataParticle)):
            sample_dict = json.loads(data_particle.generate())
        elif (isinstance(data_particle, str)):
            sample_dict = json.loads(data_particle)
        elif (isinstance(data_particle, dict)):
            sample_dict = data_particle
        else:
            raise IDKException("invalid data particle type")

        return sample_dict

    def get_data_particle_values_as_dict(self, data_particle):
        """
        Return all of the data particle values as a dictionary with the value id as the key and the value as the
        value.  This method will decimate the data, in the any characteristics other than value id and value.  i.e.
        binary.
        @param: data_particle: data particle to inspect
        @return: return a dictionary with keys and values { value-id: value }
        @raise: IDKException when missing values dictionary
        """
        sample_dict = self.convert_data_particle_to_dict(data_particle)

        values = sample_dict.get('values')
        if(not values):
            raise IDKException("Data particle missing values")

        if(not isinstance(values, list)):
            raise IDKException("Data particle values not a list")

        result = {}
        for param in values:
            if(not isinstance(param, dict)):
                raise IDKException("must be a dict")

            key = param.get('value_id')
            if(key == None):
                raise IDKException("value_id not defined")

            if(key in result.keys()):
                raise IDKException("duplicate value detected for %s" % key)

            result[key] = param.get('value')

        return result

    def assert_data_particle_keys(self, data_particle_key, test_config):
        """
        Ensure that the keys defined in the data particle key enum match
        the keys defined in the test configuration.
        @param data_particle_key: object that defines all data particle keys.
        @param test_config: dictionary containing parameter verification values
        """
        driver_keys = sorted(data_particle_key.list())
        test_config_keys = sorted(test_config.keys())

        self.assertEqual(len(driver_keys), len(test_config_keys))
        self.assertEqual(driver_keys, test_config_keys)

    def assert_data_particle_header(self, data_particle, stream_name, require_instrument_timestamp=False):
        """
        Verify a data particle header is formatted properly
        @param data_particle: version 1 data particle
        @param stream_name: version 1 data particle
        @param require_instrument_timestamp: should we verify the instrument timestamp exists
        """
        sample_dict = self.convert_data_particle_to_dict(data_particle)
        log.debug("SAMPLEDICT: %s" % sample_dict)

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME], stream_name)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID], DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertIsInstance(sample_dict[DataParticleKey.VALUES], list)

        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        self.assertIsNotNone(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP))
        self.assertIsInstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float)

        # It is highly unlikely that we should have a particle without a port agent timestamp,
        # at least that's the current assumption.
        self.assertIsNotNone(sample_dict.get(DataParticleKey.PORT_TIMESTAMP))
        self.assertIsInstance(sample_dict.get(DataParticleKey.PORT_TIMESTAMP), float)

        if(require_instrument_timestamp):
            self.assertIsNotNone(sample_dict.get(DataParticleKey.INTERNAL_TIMESTAMP))
            self.assertIsInstance(sample_dict.get(DataParticleKey.INTERNAL_TIMESTAMP), float)

    def assert_data_particle_parameters(self, data_particle, param_dict, verify_values = False):
        """
        Verify data partice parameters.  Does a quick conversion of the values to a dict
        so that common methods can operate on them.

        @param data_particle: the data particle to examine
        @param parameter_dict: dict with parameter names and types
        @param verify_values: bool should ve verify parameter values
        """
        sample_dict = self.get_data_particle_values_as_dict(data_particle)
        self.assert_parameters(sample_dict,param_dict,verify_values)

    def assert_driver_parameter_definition(self, driver, param_dict):
        """
        Verify the parameters have been defined as expected in the driver protocol.

        parameter_dict_examples:

         startup: Verifies the parameter is defined as a startup parameter
         directaccess: Verifies the parameter is defined as a direct access parameter
         readonly: Verifies the parameter is defined as a readonly parameter
         verify: Verifies the default value of the parameter

         {
             'some_key': {
                 startup: False
                 directaccess: False
                 readonly: False
                 default: some_value
             }
         }

        @param driver: driver to inspect, must have a protocol defined
        @param parameter_dict: dict with parameter names and types
        """
        self.assertIsInstance(driver, InstrumentDriver)
        self.assertIsInstance(driver._protocol, InstrumentProtocol)
        self.assertIsInstance(driver._protocol._param_dict, ProtocolParameterDict)
        self.assertIsInstance(param_dict, dict)

        pd = driver._protocol._param_dict

        for (name, config) in param_dict.items():
            log.debug("Verify parameter: %s" % name)
            self.assertIsInstance(config, dict)

            startup = config.get(ParameterTestConfigKey.STARTUP)
            da = config.get(ParameterTestConfigKey.DIRECT_ACCESS)
            readonly = config.get(ParameterTestConfigKey.READONLY)
            default = config.get(ParameterTestConfigKey.DEFAULT)

            if(da == True):
                self.assertIn(name, pd.get_direct_access_list(), msg="%s not a direct access parameters %s" % (name, pd.get_direct_access_list()))
            elif(da == False):
                self.assertNotIn(name, pd.get_direct_access_list(), msg="%s is a direct access parameters %s" % (name, pd.get_direct_access_list()))

            if(startup == True):
                self.assertIn(name, pd.get_startup_list(), msg="%s is not a startup parameter" % name)
            elif(startup == False):
                self.assertNotIn(name, pd.get_startup_list(), msg="%s is a startup parameter" % name)

            if(readonly == True):
                self.assertIn(name, pd.get_visibility_list(ParameterDictVisibility.READ_ONLY), msg="%s is not a read only parameter" % name)
            elif(readonly == False):
                self.assertIn(name, pd.get_visibility_list(ParameterDictVisibility.READ_WRITE), msg="%s is a read only parameter" % name)

            if(default):
                self.assertEqual(default, pd.get_default_value(name), "%s default value incorrect: %s != %s" % (name, default, pd.get_default_value(name)))

    def assert_parameters(self, current_parameters, param_dict, verify_values = False):
        """
        Verify the parameters contain all parameters in the parameter enum and verify the
        types match those defined in the enum.

        parameter_dict_examples:

        There is one record for each parameter. with a dict describing the parameter.

         type: the data type of the parameter.  REQUIRED
         required: is the parameter required, False == not required
         name: Name of the parameter, used for validation if we use constants when defining keys
         value: value of the parameter being validated.  This is useful for unit tests where
                parameters are known.

         Following only used for driver parameter verification
         startup: Verifies the parameter is defined as a startup parameter
         directaccess: Verifies the parameter is defined as a direct access parameter
         readonly: Verifies the parameter is defined as a readonly parameter
         verify: Verifies the default value of the parameter

         {
             'some_key': {
                 type: float,
                 required: False,
                 name: 'some_key',
                 value: 1.1

                 startup: False
                 directaccess: False
                 readonly: False
                 default: some_value
             }
         }

        required defaults to True
        name: defaults to None

        As a short cut you can define the dict with just the type.  The other fields will default
        {
            'some_key': float
        }

        This will verify the type is a float, it is required and we will not validate the key.

        @param current_parameters: list of parameters to examine
        @param parameter_dict: dict with parameter names and types
        @param verify_values: bool should ve verify parameter values
        """
        self.assertIsInstance(current_parameters, dict)
        self.assertIsInstance(param_dict, dict)

        self.assert_parameter_names(param_dict)
        self.assert_parameter_set(current_parameters, param_dict)
        self.assert_parameter_types(current_parameters, param_dict)

        if(verify_values):
            self.assert_parameter_value(current_parameters, param_dict)

    def assert_parameter_names(self, param_dict):
        """
        Verify that the names of the parameter dictionary keys match the parameter value 'name'.  This
        is useful when the parameter dict is built using constants.  If name is none then ignore.

        param_dict:

        {
             'some_key': {
                 type: float,
                 required: False,
                 name: 'some_key'
             }
         }

        @param param_dict: dictionary containing data particle parameter validation values
        """
        for key, param_def in param_dict.items():
            if(isinstance(param_def, dict)):
                name = param_def.get(ParameterTestConfigKey.NAME)
                if(name != None):
                    self.assertEqual(key, name)

    def assert_parameter_set(self, sample_values, param_dict):
        """
        Verify all required parameters appear in sample_dict as described in param_dict.  Also verify
        that there are no extra values in the sample dict that are not listed as optional in the
        param_dict
        @param sample_values: parsed data particle to inspect
        @param param_dict: dictionary containing parameter validation information
        """
        self.assertIsInstance(sample_values, dict)
        self.assertIsInstance(param_dict, dict)

        required_keys = []
        optional_keys = []

        # get all the sample parameter names
        sample_keys = sample_values.keys()
        log.info("Sample Keys: %s" % sample_keys)

        # split the parameters into optional and required
        for key, param in param_dict.items():
            if(isinstance(param, dict)):
                required = param.get(ParameterTestConfigKey.REQUIRED, True)
                if(required):
                    required_keys.append(key)
                else:
                    optional_keys.append(key)
            else:
                required_keys.append(key)

        log.info("Required Keys: %s" % required_keys)
        log.info("Optional Keys: %s" % optional_keys)

        # Lets verify all required parameters are there
        for required in required_keys:
            self.assertTrue(required in sample_keys)
            sample_keys.remove(required)

        # Now lets look for optional fields and removed them from the parameter list
        for optional in optional_keys:
            sample_keys.remove(optional)

        log.info("Unknown Keys: %s" % sample_keys)

        # If there is anything left in the sample keys then it's a problem
        self.assertEqual(len(sample_keys), 0)


    def assert_parameter_value(self, sample_values, param_dict):
        """
        Verify the value in the data particle parameter with the value in the param dict.  This test
        is useful in unit testing when the values are known.
        @param sample_dict: parsed data particle to inspect
        @param param_dict: dictionary containing parameter validation information
        """
        for (param_name, param_value) in sample_values.items():
            # get the parameter type
            param_def = param_dict.get(param_name)
            log.debug("Particle Def (%s) " % param_def)
            self.assertIsNotNone(param_def)
            if(isinstance(param_def, dict)):
                param_type = param_def.get(ParameterTestConfigKey.TYPE)
                self.assertIsNotNone(type)
            else:
                param_type = param_def

            try:
                required_value = param_def[ParameterTestConfigKey.VALUE]
                # Only test the equality if the parameter has a value.  Test for required parameters
                # happens in assert_parameter_set
                if(param_value != None):
                    self.assertEqual(param_value, required_value, msg="%s value not equal: %s != %s" % (param_name, param_value, required_value))
            except KeyError:
                # Ignore key errors
                pass


    def assert_parameter_types(self, sample_values, param_dict):
        """
        Verify all parameters in the sample_dict are of the same type as described in the param_dict
        @param sample_dict: parsed data particle to inspect
        @param param_dict: dictionary containing parameter validation information
        """
        for (param_name, param_value) in sample_values.items():
            log.debug("Data Particle Parameter (%s): %s" % (param_name, type(param_value)))

            # get the parameter type
            param_def = param_dict.get(param_name)
            self.assertIsNotNone(param_def)
            if(isinstance(param_def, dict)):
                param_type = param_def.get(ParameterTestConfigKey.TYPE)
                self.assertIsNotNone(type)
            else:
                param_type = param_def

            # is this a required parameter
            if(isinstance(param_def, dict)):
                required = param_def.get(ParameterTestConfigKey.REQUIRED, True)
            else:
                required = param_def

            if(required):
                self.assertIsNotNone(param_value, msg="%s required field None" % param_name)

            if(param_value):
                # It looks like one of the interfaces between services converts unicode to string
                # and vice versa.  So if the type is string it can be promoted to unicode so it
                # is still valid.
                if(param_type == unicode and isinstance(param_value, str)):
                    # we want type unicode, but it is a string instance.  All good
                    pass
                else:
                    self.assertIsInstance(param_value, param_type)



class InstrumentDriverTestCase(MiIntTestCase):
    """
    Base class for instrument driver tests
    """
    
    # configuration singleton
    test_config = InstrumentDriverTestConfig()
    
    @classmethod
    def initialize(cls, *args, **kwargs):
        """
        Initialize the test_configuration singleton
        """
        cls.test_config.initialize(*args,**kwargs)
    
    # Port agent process object.
    port_agent = None

    def setUp(self):
        """
        @brief Setup test cases.
        """
        log.debug("*********************************************************************")
        log.debug("Starting Test %s" % self._testMethodName)
        log.debug("*********************************************************************")
        log.debug("ID: %s" % self.id())
        log.debug("InstrumentDriverTestCase setUp")

        # Test to ensure we have initialized our test config
        if not self.test_config.initialized:
            return TestNotInitialized(msg="Tests non initialized. Missing InstrumentDriverTestCase.initalize(...)?")
            
        self.clear_events()

    def tearDown(self):
        """
        @brief Test teardown
        """
        log.debug("InstrumentDriverTestCase tearDown")

    def get_ntp_timestamp(self, unix_time=None):
        """
        Get an ntp timestamp using the passed in unix_time
        or the current time if not passed
        @param unix_time: unix timestamp to create
        @return: ntp timestamp
        """
        if(unix_time == None):
            unix_time = time.time()

        return ntplib.system_to_ntp_time(time.time())

    def clear_events(self):
        """
        @brief Clear the event list.
        """
        self.events = []

    def get_events(self, type=None):
        """
        return a list of events received.  If a type is passed then the list
        will only contain events of that type.
        @param type: type of event we are looking for
        """
        if(type == None):
            return self.events
        else:
            return [evt for evt in self.events if evt['type']==type]

    def get_sample_events(self, type=None):
        """
        Get a list of sample events, potentially of a passed in type
        @param type: what type of data particle are we looking for
        @return: list of data sample events
        """
        samples = self.get_events(DriverAsyncEvent.SAMPLE)
        if(type == None):
            return samples
        else:
            result = []
            for evt in samples:
                value = evt.get('value')
                particle = json.loads(value)
                if(particle and particle.get('stream_name') == type):
                    result.append(evt)

            return result

    def event_received(self, evt):
        """
        @brief Simple callback to catch events from the driver for verification.
        """
        self.events.append(evt)

    @classmethod
    def comm_config_file(cls):
        """
        @brief Return the path the the driver comm config yaml file.
        @return if comm_config.yml exists return the full path
        """
        repo_dir = Config().get('working_repo')
        driver_path = cls.test_config.driver_module
        p = re.compile('\.')
        driver_path = p.sub('/', driver_path)
        abs_path = "%s/%s/%s" % (repo_dir, os.path.dirname(driver_path), CommConfig.config_filename())
        
        log.debug(abs_path)
        return abs_path

    @classmethod
    def get_comm_config(cls):
        """
        @brief Create the comm config object by reading the comm_config.yml file.
        """
        log.info("get comm config")
        config_file = cls.comm_config_file()
        
        log.debug( " -- reading comm config from: %s" % config_file )
        if not os.path.exists(config_file):
            raise TestNoCommConfig(msg="Missing comm config.  Try running start_driver or switch_driver")
        
        return CommConfig.get_config_from_file(config_file)
        
    def port_agent_config(self):
        """
        return the port agent configuration
        """
        comm_config = self.get_comm_config()

        config = {
            'device_addr' : comm_config.device_addr,
            'device_port' : comm_config.device_port,

            'command_port': comm_config.command_port,
            'data_port': comm_config.data_port,

            'process_type': PortAgentProcessType.UNIX,
            'log_level': 5,
            }

        return config

    def init_port_agent(self):
        """
        @brief Launch the driver process and driver client.  This is used in the
        integration and qualification tests.  The port agent abstracts the physical
        interface with the instrument.
        @retval return the pid to the logger process
        """
        if(self.port_agent):
            log.error("Port agent already initialized")
            return

        log.debug("Startup Port Agent")

        config = self.port_agent_config()
        log.debug("port agent config: %s" % config)

        port_agent = PortAgentProcess.launch_process(config, timeout = 60, test_mode = True)

        port = port_agent.get_data_port()
        pid  = port_agent.get_pid()

        log.info('Started port agent pid %s listening at port %s' % (pid, port))

        self.addCleanup(self.stop_port_agent)
        self.port_agent = port_agent
        return port


    def stop_port_agent(self):
        """
        Stop the port agent.
        """
        log.info("Stop port agent")
        if self.port_agent:
            log.debug("found port agent, now stop it")
            self.port_agent.stop()

        self.port_agent = None

    
    def init_driver_process_client(self):
        """
        @brief Launch the driver process and driver client
        @retval return driver process and driver client object
        """
        log.info("Startup Driver Process")

        driver_config = {
            'dvr_mod'      : self.test_config.driver_module,
            'dvr_cls'      : self.test_config.driver_class,
            'workdir'      : self.test_config.working_dir,
            'comms_config' : self.port_agent_comm_config(),
            'process_type' : (self.test_config.driver_process_type,),
            'startup_config' : self.test_config.driver_startup_config
        }

        self.driver_process = DriverProcess.get_process(driver_config, True)
        self.driver_process.launch()

        # Verify the driver has started.
        if not self.driver_process.getpid():
            log.error('Error starting driver process.')
            raise InstrumentException('Error starting driver process.')

        try:
            driver_client = self.driver_process.get_client()
            driver_client.start_messaging(self.event_received)
            log.debug("before 'process_echo'")
            retval = driver_client.cmd_dvr('process_echo', 'Test.') # data=? RU
            log.debug("after 'process_echo'")

            startup_config = driver_config.get('startup_config')
            retval = driver_client.cmd_dvr('set_init_params', startup_config)

            self.driver_client = driver_client
        except Exception, e:
            self.driver_process.stop()
            log.error('Error starting driver client. %s', e)
            raise InstrumentException('Error starting driver client.')

        log.info('started its driver.')
    
    def stop_driver_process_client(self):
        """
        Stop the driver_process.
        """
        if self.driver_process:
            self.driver_process.stop()

    def port_agent_comm_config(self):
        port = self.port_agent.get_data_port()
        cmd_port = self.port_agent.get_command_port()
        return {
            'addr': 'localhost',
            'port': port,
            'cmd_port': cmd_port
        }

    #####
    # Custom assert methods
    #####

    def assert_enum_complete(self, subset, superset):
        """
        Assert that every item in an enum is in superset
        """
        self.assert_set_complete(convert_enum_to_dict(subset),
                                 convert_enum_to_dict(superset))

    def assert_set_complete(self, subset, superset):
        """
        Assert that every item in subset is in superset
        """

        # use assertTrue here intentionally because it's easier to unit test
        # this method.
        if len(superset):
            self.assertTrue(len(subset) > 0)

        for item in subset:
            self.assertTrue(item in superset)

        # This added so the unit test can set a true flag.  If we have made it
        # this far we should pass the test.
        #self.assertTrue(True)

    def assert_enum_has_no_duplicates(self, obj):
        dic = convert_enum_to_dict(obj)
        occurances  = {}
        for k, v in dic.items():
            #v = tuple(v)
            occurances[v] = occurances.get(v,0) + 1

        for k in occurances:
            if occurances[k] > 1:
                log.error(str(obj) + " has ambigous duplicate values for '" + str(k) + "'")
                self.assertEqual(1, occurances[k])

    def assert_chunker_sample(self, chunker, sample):
        '''
        Verify the chunker can parse a sample that comes in a single string
        @param chunker: Chunker to use to do the parsing
        @param sample: raw sample
        '''
        ts = self.get_ntp_timestamp()
        chunker.add_chunk(sample, ts)
        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, sample)
        self.assertEqual(ts, timestamp)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, None)

    def assert_chunker_fragmented_sample(self, chunker, sample, fragment_size = 1):
        '''
        Verify the chunker can parse a sample that comes in fragmented.  It sends bytes to the chunker
        one at a time.  This very slow for large chunks (>4k) so we don't want to increase the sample
        part size
        @param chunker: Chunker to use to do the parsing
        @param sample: raw sample
        '''
        sample_length = len(sample)
        self.assertGreater(fragment_size, 0)
        timestamps = []

        i = 0
        while(i < sample_length):
            ts = self.get_ntp_timestamp()
            timestamps.append(ts)
            end = i + fragment_size
            chunker.add_chunk(sample[i:end], ts)
            (timestamp, result) = chunker.get_next_data()
            if(result): break
            i += fragment_size

        self.assertEqual(result, sample)
        self.assertEqual(timestamps[0], timestamp)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, None)

    def assert_chunker_combined_sample(self, chunker, sample):
        '''
        Verify the chunker can parse a sample that comes in combined
        @param chunker: Chunker to use to do the parsing
        @param sample: raw sample
        '''
        ts = self.get_ntp_timestamp()
        chunker.add_chunk(sample + sample, ts)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, sample)
        self.assertEqual(timestamp, ts)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, sample)
        self.assertEqual(timestamp, ts)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, None)

    def assert_chunker_sample_with_noise(self, chunker, sample):
        '''
        Verify the chunker can parse a sample with noise on the
        front or back of sample data
        @param chunker: Chunker to use to do the parsing
        @param sample: raw sample
        '''
        noise = "this is a bunch of noise to add to the sample\r\n"
        ts = self.get_ntp_timestamp()

        # Try a sample with noise in the front
        chunker.add_chunk(noise + sample, ts)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, sample)
        self.assertEqual(timestamp, ts)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, None)

        # Now some noise in the back
        chunker.add_chunk(sample + noise, ts)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, sample)
        self.assertEqual(timestamp, ts)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, None)

        # There should still be some noise in the buffer, make sure
        # we can still take a sample.
        chunker.add_chunk(sample + noise, ts)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, sample)
        self.assertEqual(timestamp, ts)

        (timestamp, result) = chunker.get_next_data()
        self.assertEqual(result, None)


class InstrumentDriverUnitTestCase(InstrumentDriverTestCase):
    """
    Base class for instrument driver unit tests
    """
    _data_particle_received = []

    def clear_data_particle_queue(self):
        """
        Reset the queue which stores data particles received via our
        custome event callback.
        """
        self._data_particle_received = []

    def _got_data_event_callback(self, event):
        """
        Event call back method sent to the driver.  It simply grabs a sample event and pushes it
        into the data particle queue
        """
        event_type = event['type']
        if event_type == DriverAsyncEvent.SAMPLE:
            sample_value = event['value']
            particle_dict = json.loads(sample_value)
            self._data_particle_received.append(sample_value)

    def compare_parsed_data_particle(self, particle_type, raw_input, happy_structure):
        """
        Compare a data particle created with the raw input string to the structure
        that should be generated.
        
        @param The data particle class to create
        @param raw_input The input string that is instrument-specific
        @param happy_structure The structure that should result from parsing the
            raw input during DataParticle creation
        """
        port_timestamp = happy_structure[DataParticleKey.PORT_TIMESTAMP]
        if DataParticleKey.INTERNAL_TIMESTAMP in happy_structure:
            internal_timestamp = happy_structure[DataParticleKey.INTERNAL_TIMESTAMP]        
            test_particle = particle_type(raw_input, port_timestamp=port_timestamp,
                                          internal_timestamp=internal_timestamp)
        else:
            test_particle = particle_type(raw_input, port_timestamp=port_timestamp)
            
        parsed_result = test_particle.generate()
        decoded_parsed = json.loads(parsed_result)
        
        driver_time = decoded_parsed[DataParticleKey.DRIVER_TIMESTAMP]
        happy_structure[DataParticleKey.DRIVER_TIMESTAMP] = driver_time
        
        # run it through json so unicode and everything lines up
        standard = json.dumps(happy_structure, sort_keys=True)

        self.assertEqual(parsed_result, standard)

    def assert_force_state(self, driver, protocol_state):
        """
        For the driver state to protocol_state
        @param driver: Instrument driver instance.
        @param protocol_state: State to transistion to
        """
        driver.test_force_state(state = protocol_state)
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, protocol_state)

    def assert_driver_connected(self, driver, initial_protocol_state = DriverProtocolState.AUTOSAMPLE):
        """
        Check to see if the driver is connected, if it isn't then initialize the driver.  Finally
        force the instrument state to the initial_protocol_state.
        @param driver: Instrument driver instance.
        @param initial_protocol_state: the state to force the driver too
        """
        current_state = driver.get_resource_state()
        if(current_state == DriverConnectionState.UNCONFIGURED):
            self.assert_initialize_driver(driver, initial_protocol_state)
        else:
            self.assert_force_state(driver, initial_protocol_state)

    def assert_initialize_driver(self, driver, initial_protocol_state = DriverProtocolState.AUTOSAMPLE):
        """
        Initialize an instrument driver with a mock port agent.  This will allow us to test the
        got data method.  Will the instrument, using test mode, through it's connection state
        machine.  End result, the driver will be in test mode and the connection state will be
        connected.
        @param driver: Instrument driver instance.
        @param initial_protocol_state: the state to force the driver too
        """
        mock_port_agent = Mock(spec=PortAgentClient)

        # Put the driver into test mode
        driver.set_test_mode(True)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)

        # Now configure the driver with the mock_port_agent, verifying
        # that the driver transitions to that state
        config = {'mock_port_agent' : mock_port_agent}
        driver.configure(config = config)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)

        # Invoke the connect method of the driver: should connect to mock
        # port agent.  Verify that the connection FSM transitions to CONNECTED,
        # (which means that the FSM should now be reporting the ProtocolState).
        driver.connect()
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        # Force the instrument into a known state
        self.assert_force_state(driver, initial_protocol_state)

    def assert_raw_particle_published(self, driver, assert_callback, verify_values = False):
        """
        Verify that every call to got_data publishes a raw data particle

        Create a port agent packet, send it through got_data, then finally grab the data particle
        from the data particle queue and verify it using the passed in assert method.
        @param driver: instrument driver with mock port agent client
        @param verify_values: Should we validate values?
        """
        sample_data = SAMPLE_RAW_DATA
        log.debug("Sample to publish: %s" % sample_data)

        # Create and populate the port agent packet.
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(sample_data)
        port_agent_packet.pack_header()

        self.clear_data_particle_queue()

        # Push the data into the driver
        driver._protocol.got_raw(port_agent_packet)
        self.assertEqual(len(self._data_particle_received), 1)
        particle = self._data_particle_received.pop()
        particle_dict = json.loads(particle)
        log.debug("Raw Particle: %s" % particle_dict)

        # Verify the data particle
        self.assert_particle_raw(particle_dict, verify_values)


    def assert_particle_published(self, driver, sample_data, particle_assert_method, verify_values = False):
        """
        Verify that we can send data through the port agent and the the correct particles
        are generated.

        Create a port agent packet, send it through got_data, then finally grab the data particle
        from the data particle queue and verify it using the passed in assert method.
        @param driver: instrument driver with mock port agent client
        @param sample_data: the byte string we want to send to the driver
        @param particle_assert_method: assert method to validate the data particle.
        @param verify_values: Should we validate values?
        """
        ts = ntplib.system_to_ntp_time(time.time())

        log.debug("Sample to publish: %s" % sample_data)
        # Create and populate the port agent packet.
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(sample_data)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()

        self.clear_data_particle_queue()

        # Push the data into the driver
        driver._protocol.got_data(port_agent_packet)

        # Find all particles of the correct data particle types (not raw)
        particles = []
        for p in self._data_particle_received:
            particle_dict = json.loads(p)
            stream_type = particle_dict.get('stream_name')
            self.assertIsNotNone(stream_type)
            if(stream_type != CommonDataParticleType.RAW):
                particles.append(p)

        log.debug("Non raw particles: %s " % particles)
        self.assertEqual(len(particles), 1)

        # Verify the data particle
        particle_assert_method(particles.pop(), verify_values)


    def assert_capabilities(self, driver, capabilities):
        """
        Verify all capabilities expected are in the FSM.  Then verify that the capabilities
        available for each state.
        @param driver: a mocked up driver
        @param capabilities: dictionary with protocol state as the key and a list as expected capabilities
        """
        self.assert_protocol_states(driver,capabilities)
        self.assert_all_capabilities(driver,capabilities)
        self.assert_state_capabilities(driver,capabilities)

    def assert_protocol_states(self, driver, capabilities):
        """
        Verify that the protocol states defined in the driver match the list of states in the
        capabilities dictionary.
        @param driver: a mocked up driver
        @param capabilities: dictionary with protocol state as the key and a list as expected capabilities
        """
        self.assert_driver_connected(driver)
        fsm_states = sorted(driver._protocol._protocol_fsm.states.list())
        self.assertTrue(fsm_states)

        expected_states = sorted(capabilities.keys())

        log.debug("Defined Protocol States: %s" % fsm_states)
        log.debug("Expected Protocol States: %s" % expected_states)

        self.assertEqual(fsm_states, expected_states)


    def assert_all_capabilities(self, driver, capabilities):
        """
        Build a list of all the capabilities in the passed in dict and verify they are all availalbe
        in the FSM
        @param driver: a mocked up driver
        @param capabilities: dictionary with protocol state as the key and a list as expected capabilities
        """
        self.maxDiff = None
        self.assert_driver_connected(driver)
        all_capabilities = sorted(driver._protocol._protocol_fsm.get_events(current_state=False))
        expected_capabilities = []

        for (state, capability_list) in capabilities.items():
            for s in capability_list:
                if(not s in expected_capabilities):
                    expected_capabilities.append(s)

        expected_capabilities.sort()

        log.debug("All Reported Capabilities: %s" % all_capabilities)
        log.debug("All Expected Capabilities: %s" % expected_capabilities)

        self.assertEqual(all_capabilities, expected_capabilities)


    def assert_state_capabilities(self, driver, capabilities):
        """
        Walk through all instrument states and verify fsm capabilities available
        as reported by the driver.
        @param driver: a mocked up driver
        @param capabilities: dictionary with protocol state as the key and a list as expected capabilities
        """
        self.assert_driver_connected(driver)
        driver.set_test_mode(True)

        # Verify state specific capabilities
        for (state, capability_list) in capabilities.items():
            self.assert_force_state(driver, state)
            reported_capabilities = sorted(driver._protocol._protocol_fsm.get_events(current_state=True))
            expected_capabilities = sorted(capability_list)

            log.debug("Current Driver State: %s" % state)
            log.debug("Expected Capabilities: %s" % expected_capabilities)
            log.debug("Reported Capabilities: %s" % reported_capabilities)

            self.assertEqual(reported_capabilities, expected_capabilities)

class InstrumentDriverIntegrationTestCase(InstrumentDriverTestCase):   # Must inherit from here to get _start_container
    def setUp(self):
        """
        @brief Setup test cases.
        """
        log.debug("InstrumentDriverIntegrationTestCase.setUp")
        self.init_port_agent()
        InstrumentDriverTestCase.setUp(self)

        log.debug("InstrumentDriverIntegrationTestCase setUp")
        self.init_driver_process_client()
        self.clear_events()

    def tearDown(self):
        """
        @brief Test teardown
        """
        log.debug("InstrumentDriverIntegrationTestCase tearDown")
        self.stop_driver_process_client()

        InstrumentDriverTestCase.tearDown(self)

    ###
    #   Common assert methods
    ###
    def assert_current_state(self, target_state):
        """
        Verify the driver state
        @param state:
        @return:
        """
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, target_state)

    def assert_initialize_driver(self, final_state=DriverProtocolState.COMMAND):
        """
        Walk an uninitialized driver through it's initialize process.  Verify the final
        state is command mode.  If the final state is auto sample then we will stop
        which should land us in autosample
        """
        log.info("test_connect test started")

        # Test the driver is in state unconfigured.
        self.assert_current_state(DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        self.assert_current_state(DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        self.assert_current_state(DriverProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # If we are in streaming mode then stop streaming
        state = self.driver_client.cmd_dvr('get_resource_state')
        if(state == DriverProtocolState.AUTOSAMPLE and final_state != DriverProtocolState.AUTOSAMPLE):
            log.debug("Stop autosample because we want to be in command mode")
            reply = self.driver_client.cmd_dvr('execute_resource', DriverEvent.STOP_AUTOSAMPLE)
            state = self.driver_client.cmd_dvr('get_resource_state')

        if(state == DriverProtocolState.COMMAND and final_state != DriverProtocolState.COMMAND):
            log.debug("Start autosample because we don't want to be in command mode")
            reply = self.driver_client.cmd_dvr('execute_resource', DriverEvent.START_AUTOSAMPLE)
            state = self.driver_client.cmd_dvr('get_resource_state')

        log.debug("initialize final state: %s" % state)
        # Test the driver is in the correct mode
        if(final_state == DriverProtocolState.AUTOSAMPLE):
            self.assertEqual(state, DriverProtocolState.AUTOSAMPLE)
        else:
            self.assertEqual(state, DriverProtocolState.COMMAND)

    def assert_get(self, param, value=None, pattern=None):
        """
        Verify we can get a parameter and compare the fetched value
        with the expected value.
        @param param: parameter to set
        @param value: expected parameter value
        @param pattern: expected parameter pattern
        @return value of the parameter
        """
        reply = self.driver_client.cmd_dvr('get_resource', [param])
        self.assertIsInstance(reply, dict)
        return_value = reply.get(param)

        if(value != None):
            self.assertEqual(return_value, value, msg="%s no value match (%s != %s)" % (param, return_value, value))
        elif(pattern != None):
            self.assertRegexpMatches(str(return_value), pattern, msg="%s no value match (%s != %s)" % (param, return_value, value))

        return return_value

    def assert_set(self, param, value, no_get=False):
        """
        Verify we can set a parameter and then do a get to confirm. Also, unless
        no_get is specified, verify a config change event is sent when values
        change and none when they aren't changed.
        @param param: parameter to set
        @param param: no_get if true don't verify set with a get.
        @param value: what to set the parameter too
        """
        if no_get:
            reply = self.driver_client.cmd_dvr('set_resource', {param: value})
            self.assertIsNone(reply, None)
        else:
            log.debug("assert_set, check values and events")
            self.clear_events()
            current_value = self.assert_get(param)
            config_change = current_value != value

            log.debug("current value: %s new value: %s" % (current_value, value))
            self.assert_set(param, value, True)
            self.assert_get(param, value)

            time.sleep(1)
            events = self.get_events(DriverAsyncEvent.CONFIG_CHANGE)

            log.debug("got config change events: %d" % len(events))
            if(config_change):
                self.assertTrue(len(events) > 0)
            else:
                self.assertEqual(len(events), 0)

            # Let's set it again.  This time we know it shouldn't generate a
            # config change event
            self.clear_events()
            self.assert_set(param, value, True)
            time.sleep(1)
            log.debug("pass #2 got config change events: %d" % len(events))
            events = self.get_events(DriverAsyncEvent.CONFIG_CHANGE)
            self.assertEqual(len(events), 0)

            self.assert_get(param, value)

    def assert_set_bulk(self, param_dict):
        """
        Verify we can bulk set parameters.  First bulk set the parameters and
        then verify with individual gets.
        @param param_dict: dictionary with parameter as key with it's value.
        """
        self.assertIsInstance(param_dict, dict)

        reply = self.driver_client.cmd_dvr('set_resource', param_dict)
        self.assertIsNone(reply, None)

        for (key, value) in param_dict.items():
            self.assert_get(key, value)

    def assert_set_bulk_exception(self, param_dict, error_regex=None, exception_class=InstrumentParameterException):
        """
        Verify a bulk set raises an exception
        then verify with individual gets.
        @param param_dict: dictionary with parameter as key with it's value.
        @param error_regex: error message pattern to match
        @param exception_class: class of the exception raised
        """
        if(error_regex):
            with self.assertRaisesRegexp(exception_class, error_regex):
                self.assert_set_bulk(param_dict)
        else:
            with self.assertRaises(exception_class):
                self.assert_set_bulk(param_dict)

    def assert_set_readonly(self, param, value='dummyvalue', exception_class=InstrumentParameterException):
        """
        Verify that a set command raises an exception on set.
        @param param: parameter to set
        @param value: what to set the parameter too
        """
        self.assert_set_exception(param, value, exception_class=exception_class)

    def assert_set_exception(self, param, value='dummyvalue', error_regex=None, exception_class=InstrumentParameterException):
        """
        Verify that a set command raises an exception on set.
        @param param: parameter to set
        @param value: what to set the parameter too
        @param error_regex: error message pattern to match
        @param exception_class: class of the exception raised
        """
        if(error_regex):
            with self.assertRaisesRegexp(exception_class, error_regex):
                reply = self.driver_client.cmd_dvr('set_resource', {param: value})
        else:
            with self.assertRaises(exception_class):
                reply = self.driver_client.cmd_dvr('set_resource', {param: value})

    def assert_driver_command(self, command, expected=None, regex=None, value_function=None, state=None, delay=0):
        """
        Verify that we can run a command and that the reply matches if we have
        passed on in.  If we couldn't execute a command we assume an exception
        will be thrown.
        @param command: driver command to execute
        @param expected: expected reply from the command
        @param regex: regex to match reply
        """
        # Execute the command
        reply = self.driver_client.cmd_dvr('execute_resource', command, )
        log.debug("Execute driver command: %s" % command)
        log.debug("Reply type: %s" % type(reply))

        if(delay):
            log.debug("sleeping for a bit: %d" % delay)
            time.sleep(delay)

        # Get the value to check in the reply
        if(reply != None):
            if(value_function == None):
                self.assertIsInstance(reply, tuple)
                value = reply[1]
            else:
                value = value_function(reply)

        if(expected != None):
            log.debug("command reply: %s" % value)
            self.assertIsNotNone(value)
            self.assertEqual(value, expected)

        if(regex != None):
            log.debug("command reply: %s" % value)
            self.assertIsNotNone(value)
            self.assertRegexpMatches(value, regex)

        if(state != None):
            self.assert_current_state(state)

    def assert_driver_command_exception(self, command, error_regex=None, exception_class=InstrumentStateException):
        """
        Verify a driver command throws an exception
        then verify with individual gets.
        @param command: driver command to execute
        @param error_regex: error message pattern to match
        @param exception_class: class of the exception raised
        """
        if(error_regex):
            with self.assertRaisesRegexp(exception_class, error_regex):
                self.driver_client.cmd_dvr(command)
        else:
            with self.assertRaises(exception_class):
                self.driver_client.cmd_dvr(command)

    def assert_particle_generation(self, command, particle_type, particle_callback, delay=1, timeout=None):
        """
        Verify we can generate a particle via a command.
        @param command: command used to generate the particle
        @param particle_type: particle type we are looking for
        @param particle_callback: callback used to validate the particle
        @param timeout: command timeout
        """
        self.assert_driver_command(command, delay=delay)

        samples = self.get_sample_events(particle_type)
        self.assertGreaterEqual(len(samples), 1)

        sample = samples.pop()
        self.assertIsNotNone(sample)

        value = sample.get('value')
        self.assertIsNotNone(value)

        particle = json.loads(value)
        self.assertIsNotNone(particle)

        particle_callback(particle)

    def assert_async_particle_generation(self, particle_type, particle_callback, timeout=10):
        """
        Watch the event queue for a published data particles.
        @param particle_type: particle type we are looking for
        @param particle_callback: callback used to validate the particle
        @param timeout: how long should we wait for a particle
        """
        end_time = time.time() + timeout
        samples = []

        while(len(samples) == 0):
            samples = self.get_sample_events(particle_type)
            log.debug("Found %d samples" % len(samples))
            if(len(samples) > 1):
                sample = samples.pop()
                self.assertIsNotNone(sample)

                value = sample.get('value')
                self.assertIsNotNone(value)

                particle = json.loads(value)
                self.assertIsNotNone(particle)

                # So we have found one particle and verified it.  We are done here!
                particle_callback(particle)
                return

            self.assertGreater(end_time, time.time(), msg="Timeout waiting for sample")
            time.sleep(.3)

    def assert_scheduled_event(self, job_name, assert_callback, autosample_command=None, delay=5):
        """
        Verify that a scheduled event can be triggered and use the
        assert callback to verify that it worked. If an auto sample command
        is passed then put the driver in streaming mode.  When transitioning
        to streaming you may need to increase the delay.
        @param job_name: name of the job to schedule
        @param assert_callback: verification callback
        @param autosample_command: command to put us in autosample mode
        @param delay: time to wait before the event is triggered in seconds
        """
        # Build a scheduled job for 'delay' seconds from now
        dt = datetime.datetime.now() + datetime.timedelta(0,delay)

        scheduler_config = {
            DriverSchedulerConfigKey.TRIGGER: {
                DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.ABSOLUTE,
                DriverSchedulerConfigKey.DATE: "%s" % dt
            }
        }

        # get the current driver configuration
        config = self.driver_client.cmd_dvr('get_init_params')

        # Add the scheduled job
        if(not config):
            config = {}
        if(not config.get(DriverStartupConfigKey.SCHEDULER)):
            config[DriverStartupConfigKey.SCHEDULER] = {}

        config[DriverStartupConfigKey.SCHEDULER][job_name] = scheduler_config

        # Currently the only way to setup schedulers is via the startup config
        # mechanism.  We may need to expose scheduler specific capability in the
        # future, but this should work in the intrum.
        self.driver_client.cmd_dvr('set_init_params', config)
        log.debug("SET CONFIG, set_init_params: %s" % config)

        # Walk the driver to command mode.
        self.assert_initialize_driver()

        # We explicitly call apply startup params because we don't know if the
        # driver does it for us.  It should, but it is tested in another test.
        self.driver_client.cmd_dvr('apply_startup_params')

        # Transition to autosample if command supplied
        if(autosample_command):
            self.assert_driver_command(autosample_command)

        # Ensure we have at least 5 seconds before the event should fire
        safe_time = datetime.datetime.now() + datetime.timedelta(0,5)
        self.assertGreaterEqual(dt, safe_time, msg="Trigger time already in the past. Increase your delay")

        time.sleep(2)

        # Now verify that the job is triggered and it does what we think it should
        assert_callback()

    ###
    #   Common Integration Tests
    ###
    def test_driver_process(self):
        """
        @Brief Test for correct launch of driver process and communications, including asynchronous driver events.
        """

        log.info("Ensuring driver process was started properly ...")
        
        # Verify processes exist.
        self.assertNotEqual(self.driver_process, None)
        drv_pid = self.driver_process.getpid()
        self.assertTrue(isinstance(drv_pid, int))
        
        self.assertNotEqual(self.port_agent, None)
        pagent_pid = self.port_agent.get_pid()
        self.assertTrue(isinstance(pagent_pid, int))
        
        # Send a test message to the process interface, confirm result.
        log.debug("before 'process_echo'")
        reply = self.driver_client.cmd_dvr('process_echo')
        log.debug("after 'process_echo'")
        self.assert_(reply.startswith('ping from resource ppid:'))

        reply = self.driver_client.cmd_dvr('driver_ping', 'foo')
        self.assert_(reply.startswith('driver_ping: foo'))

        # Test the driver is in state unconfigured.
        # TODO: Add this test back in after driver code is merged from coi-services
        #state = self.driver_client.cmd_dvr('get_current_state')
        #self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
                
        # Test the event thread publishes and client side picks up events.
        events = [
            'I am important event #1!',
            'And I am important event #2!'
            ]
        reply = self.driver_client.cmd_dvr('test_events', events=events)
        gevent.sleep(1)
        
        # Confirm the events received are as expected.
        self.assertEqual(self.events, events)

        # Test the exception mechanism.
        with self.assertRaises(InstrumentException):
            exception_str = 'Oh no, something bad happened!'
            reply = self.driver_client.cmd_dvr('test_exceptions', exception_str)

    def test_disconnect(self):
        """
        Test that we can disconnect from a driver
        """
        self.assert_initialize_driver()

        reply = self.driver_client.cmd_dvr('disconnect')
        self.assertEqual(reply, None)

        self.assert_current_state(DriverConnectionState.DISCONNECTED)


class InstrumentDriverQualificationTestCase(InstrumentDriverTestCase):
    def setUp(self):
        """
        @brief Setup test cases.
        """
        InstrumentDriverTestCase.setUp(self)

        self.init_port_agent()
        self.instrument_agent_manager = InstrumentAgentClient();
        self.instrument_agent_manager.start_container(deploy_file=self.test_config.container_deploy_file)

        self.container = self.instrument_agent_manager.container

        log.debug("Packet Config: %s" % self.test_config.instrument_agent_packet_config)
        self.data_subscribers = InstrumentAgentDataSubscribers(
            packet_config=self.test_config.instrument_agent_packet_config,
        )
        self.event_subscribers = InstrumentAgentEventSubscribers(instrument_agent_resource_id=self.test_config.instrument_agent_resource_id)

        self.init_instrument_agent_client()

        self.event_subscribers.events_received = []
        self.data_subscribers.start_data_subscribers()

        log.debug("********* setUp complete.  Begin Testing *********")

    def tearDown(self):
        """
        @brief Test teardown
        """
        log.debug("InstrumentDriverQualificationTestCase tearDown")

        self.assert_reset()
        self.instrument_agent_manager.stop_container()
        self.event_subscribers.stop()
        self.data_subscribers.stop_data_subscribers()
        InstrumentDriverTestCase.tearDown(self)

    def init_instrument_agent_client(self):
        log.info("Start Instrument Agent Client")

        # Driver config
        driver_config = {
            'dvr_mod' : self.test_config.driver_module,
            'dvr_cls' : self.test_config.driver_class,
            'workdir' : self.test_config.working_dir,
            'process_type' : (self.test_config.driver_process_type,),
            'comms_config' : self.port_agent_comm_config(),
            'startup_config' : self.test_config.driver_startup_config
        }

        # Create agent config.
        agent_config = {
            'driver_config' : driver_config,
            'stream_config' : self.data_subscribers.stream_config,
            'agent'         : {'resource_id': self.test_config.instrument_agent_resource_id},
            'test_mode' : True  ## Enable a poison pill. If the spawning process dies
            ## shutdown the daemon process.
        }

        # Start instrument agent client.
        self.instrument_agent_manager.start_client(
            name=self.test_config.instrument_agent_name,
            module=self.test_config.instrument_agent_module,
            cls=self.test_config.instrument_agent_class,
            config=agent_config,
            resource_id=self.test_config.instrument_agent_resource_id,
            deploy_file=self.test_config.container_deploy_file
        )

        self.instrument_agent_client = self.instrument_agent_manager.instrument_agent_client

    def _common_agent_commands(self, agent_state):
        '''
        list of common agent parameters for a agent state
        @return: list of agent parameters
        @raise: KeyError for undefined agent state
        '''
        capabilities = {
            ResourceAgentState.UNINITIALIZED: [
                ResourceAgentEvent.INITIALIZE
            ],
            ResourceAgentState.COMMAND: [
                ResourceAgentEvent.CLEAR,
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.GO_DIRECT_ACCESS,
                ResourceAgentEvent.GO_INACTIVE,
                ResourceAgentEvent.PAUSE
            ],
            ResourceAgentState.STREAMING: [
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.GO_INACTIVE
            ],

            ResourceAgentState.DIRECT_ACCESS: [
                ResourceAgentEvent.GO_COMMAND
            ]
        }

        return capabilities[agent_state]

    def _common_da_resource_commands(self):
        """
        return a list of the common resource commands for DA
        @return: list of da commands
        """
        return [
        ]

    def _common_agent_parameters(self):
        '''
        list of common agent parameters
        @return: list of agent parameters
        '''
        return ['alarms', 'example', 'pubfreq', 'streams']

    def assert_agent_state(self, target_state):
        """
        Verify the current agent state
        @param target_state: What we expect the agent state to be
        """
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, target_state)

    def assert_agent_command(self, command, args=None, timeout=None):
        """
        Verify an agent command throws an exception
        @param command: driver command to execute
        @param args: kwargs to pass to the agent command object
        """
        cmd = AgentCommand(command=command, kwargs=args)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=timeout)

    def assert_execute_resource(self, command, args=None, timeout=None):
        """
        Verify an agent command throws an exception
        @param command: driver command to execute
        @param args: kwargs to pass to the agent command object
        """
        cmd = AgentCommand(command=command, kwargs=args)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=timeout)

    def assert_agent_command_exception(self, command, error_regex=None, exception_class=InstrumentStateException, timeout=None):
        """
        Verify an agent command throws an exception
        @param command: driver command to execute
        @param error_regex: error message pattern to match
        @param exception_class: class of the exception raised
        """
        if(error_regex):
            with self.assertRaisesRegexp(exception_class, error_regex):
                cmd = AgentCommand(command=command)
                retval = self.instrument_agent_client.execute_agent(cmd, timeout=timeout)
        else:
            with self.assertRaises(exception_class):
                cmd = AgentCommand(command=command)
                retval = self.instrument_agent_client.execute_agent(cmd, timeout=timeout)

    def assert_v1_particle_headers(self, sample_dict):
        """
        Assert that a particle's header fields are valid and sufficiently
        complete for a basic particle.
        @param sample_dict The python dictionary form of a particle
        """
        self.assertTrue(isinstance(sample_dict, dict)) 
        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
            DataParticleValue.PARSED)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))


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
        expected_agent_param = capabilities.get(AgentCapabilityType.AGENT_PARAMETER)
        expected_agent_param.sort()
        expected_res_cmd = capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)
        expected_res_cmd.sort()
        expected_res_param = capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)
        expected_res_param.sort()
        expected_res_int = capabilities.get(AgentCapabilityType.RESOURCE_INTERFACE)
        expected_res_int.sort()
        
        # go get the active capabilities
        retval = self.instrument_agent_client.get_capabilities()
        agt_cmds, agt_pars, res_cmds, res_iface, res_pars = sort_capabilities(retval)

        log.debug("Agent Commands: %s " % str(agt_cmds))
        log.debug("Compared to: %s", capabilities.get(AgentCapabilityType.AGENT_COMMAND))
        log.debug("Agent Parameters: %s " % str(agt_pars))
        log.debug("Compared to: %s", capabilities.get(AgentCapabilityType.AGENT_PARAMETER))
        log.debug("Resource Commands: %s " % str(res_cmds))
        log.debug("Compared to: %s", capabilities.get(AgentCapabilityType.RESOURCE_COMMAND))
        log.debug("Resource Interface: %s " % str(res_iface))
        log.debug("Compared to: %s", capabilities.get(AgentCapabilityType.RESOURCE_INTERFACE))
        log.debug("Resource Parameter: %s " % str(res_pars))
        log.debug("Compared to: %s", capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER))
        
        # Compare to what we are supposed to have
        self.assertEqual(expected_agent_cmd, agt_cmds)
        self.assertEqual(expected_agent_param, agt_pars)
        self.assertEqual(expected_res_cmd, res_cmds)
        self.assertEqual(expected_res_int, res_iface)
        self.assertEqual(expected_res_param, res_pars)

    def assert_sample_polled(self, sample_data_assert, sample_queue, timeout = 10):
        """
        Test observatory polling function.

        Verifies the acquire_status command.
        """
        self.assert_enter_command_mode()
        self.assert_particle_polled(DriverEvent.ACQUIRE_SAMPLE, sample_data_assert, sample_queue, timeout, 3)

    def assert_particle_polled(self, command, data_particle_assert, sample_queue, timeout=10, sample_count=1):
        """
        Verify that a command generates the expected data particle
        @param command: command to execute that will generate the particle
        @param data_particle_assert: callback to assert method to verify the particle
        @param sample_queue: sample queue to watch for particles
        @param timeout: max time to wait for samples
        @param sample_count: how many times to call the command
        """
        # make sure there aren't any junk samples in the parsed
        # data queue.
        log.debug("Acqire Sample")
        self.data_subscribers.clear_sample_queue(sample_queue)

        for i in range(0, sample_count):
            cmd = AgentCommand(command=command)
            reply = self.instrument_agent_client.execute_resource(cmd, timeout=timeout)

        # Watch the parsed data queue and return once three samples
        # have been read or the default timeout has been reached.
        samples = self.data_subscribers.get_samples(sample_queue, sample_count, timeout = timeout)
        self.assertGreaterEqual(len(samples), sample_count)
        log.trace("SAMPLE: %s" % samples)

        # Verify
        for sample in samples:
            data_particle_assert(sample)

    def assert_sample_autosample(self, sample_data_assert, sample_queue,
                                 timeout=GO_ACTIVE_TIMEOUT, sample_count=3):
        """
        Test instrument driver execute interface to start and stop streaming
        mode.

        This command is only useful for testing one stream produced in
        streaming mode at a time.  If your driver has multiple streams
        then you will need to call this method more than once or use a
        different test.
        """
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        self.assert_enter_command_mode()

        self.data_subscribers.clear_sample_queue(sample_queue)

        # Begin streaming.
        self.assert_start_autosample()

        # Assert we got 3 samples.
        samples = self.data_subscribers.get_samples(sample_queue, sample_count, timeout = timeout)
        self.assertGreaterEqual(len(samples), sample_count)

        for sample in samples:
            log.debug("SAMPLE: %s" % sample)
            sample_data_assert(sample)

        # Halt streaming.
        self.assert_stop_autosample()

    def assert_sample_async(self, sampleDataAssert, sampleQueue,
                                  timeout=GO_ACTIVE_TIMEOUT, sample_count=1):
        """
        Watch the data queue for sample data.

        This command is only useful for testing one stream produced in
        streaming mode at a time.  If your driver has multiple streams
        then you will need to call this method more than once or use a
        different test.
        """
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        self.data_subscribers.clear_sample_queue(sampleQueue)

        samples = self.data_subscribers.get_samples(sampleQueue, sample_count, timeout = timeout)
        self.assertGreaterEqual(len(samples), sample_count)

        for s in samples:
            log.debug("SAMPLE: %s" % s)
            sampleDataAssert(s)

    def assert_reset(self):
        '''
        Exist active state
        '''
        log.debug("Reset Agent Now!")

        state = self.instrument_agent_client.get_agent_state()
        log.debug("Current State: %s" % state)

        if(state == ResourceAgentState.DIRECT_ACCESS):
            self.assert_direct_access_stop_telnet()

        # reset the instrument if it has been initialized
        if(state != ResourceAgentState.UNINITIALIZED):
            self.assert_agent_command(ResourceAgentEvent.RESET)
            self.assert_agent_state(ResourceAgentState.UNINITIALIZED)

    def assert_get_parameter(self, name, value):
        '''
        verify that parameters are got correctly.  Assumes we are in command mode.
        '''
        getParams = [ name ]

        result = self.instrument_agent_client.get_resource(getParams,
                                                           timeout=GET_TIMEOUT)

        self.assertEqual(result[name], value)

    def assert_set_parameter(self, name, value, verify=True):
        '''
        verify that parameters are set correctly.  Assumes we are in command mode.
        '''
        setParams = { name : value }
        getParams = [ name ]

        self.instrument_agent_client.set_resource(setParams,
                                                  timeout=SET_TIMEOUT)

        if(verify):
            result = self.instrument_agent_client.get_resource(getParams,
                                                               timeout=GET_TIMEOUT)
            self.assertEqual(result[name], value)

    def assert_read_only_parameter(self, name, value):
        '''
        verify that parameters are read only.  Ensure an exception is thrown
        when set is called and that the value returned is the same as the
        passed in value.
        '''
        setParams = { name : value }
        getParams = [ name ]

        # Call set, but verify the command failed.
        #self.instrument_agent_client.set_resource(setParams)

        # Call get and verify the value is correct.
        #result = self.instrument_agent_client.get_resource(getParams)
        #self.assertEqual(result[name], value)

    def assert_stop_autosample(self, timeout=GO_ACTIVE_TIMEOUT):
        '''
        Enter autosample mode from command
        '''
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)

        # Stop streaming.
        cmd = AgentCommand(command=DriverEvent.STOP_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=timeout)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

    def assert_start_autosample(self, timeout=GO_ACTIVE_TIMEOUT):
        '''
        Enter autosample mode from command
        '''
        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, DriverProtocolState.COMMAND)

        # Begin streaming.
        cmd = AgentCommand(command=DriverEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=timeout)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)

    def assert_enter_command_mode(self, timeout=GO_ACTIVE_TIMEOUT):
        '''
        Walk through IA states to get to command mode from uninitialized
        '''
        state = self.instrument_agent_client.get_agent_state()
        if state == ResourceAgentState.UNINITIALIZED:

            with self.assertRaises(Conflict):
                res_state = self.instrument_agent_client.get_resource_state()
    
            cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
            retval = self.instrument_agent_client.execute_agent(cmd, timeout=timeout)
            state = self.instrument_agent_client.get_agent_state()
            self.assertEqual(state, ResourceAgentState.INACTIVE)
            log.info("Sent INITIALIZE; IA state = %s", state)
    
            res_state = self.instrument_agent_client.get_resource_state()
            self.assertEqual(res_state, DriverConnectionState.UNCONFIGURED)
    
            cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
            retval = self.instrument_agent_client.execute_agent(cmd, timeout=timeout)
            state = self.instrument_agent_client.get_agent_state()
            log.info("Sent GO_ACTIVE; IA state = %s", state)

            cmd = AgentCommand(command=ResourceAgentEvent.RUN)
            retval = self.instrument_agent_client.execute_agent(cmd)

        # The instrument is in autosample; take it out of autosample,
        # which will cause the driver and agent to transition to COMMAND
        if state == ResourceAgentState.STREAMING:
            self.assert_stop_autosample()

        state = self.instrument_agent_client.get_agent_state()
        log.info("Sent RUN; IA state = %s", state)
        self.assertEqual(state, ResourceAgentState.COMMAND)

        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, DriverProtocolState.COMMAND)

    def assert_direct_access_start_telnet(self, timeout=600):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_enter_command_mode()

        # go direct access
        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
            kwargs={'session_type': DirectAccessTypes.telnet,
                    'session_timeout':timeout,
                    'inactivity_timeout':timeout})
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=timeout)
        log.warn("go_direct_access retval=" + str(retval.result))

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.DIRECT_ACCESS)

        # start 'telnet' client with returned address and port
        self.tcp_client = TcpClient(retval.result['ip_address'], retval.result['port'])

        self.assertTrue(self.tcp_client.expect("Username: " ))
        self.tcp_client.send_data("bob\r\n")

        self.assertTrue(self.tcp_client.expect("token: "))
        self.tcp_client.send_data(retval.result['token'] + "\r\n",)

        self.assertTrue(self.tcp_client.telnet_handshake())

        self.assertTrue(self.tcp_client.expect("connected\r\n"))
        
    def assert_direct_access_stop_telnet(self, timeout=GO_ACTIVE_TIMEOUT):
        '''
        Exit out of direct access mode.  We do this by simply changing
        state to command mode.
        @return:
        '''       
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.DIRECT_ACCESS)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_COMMAND)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=timeout) # ~9s to run

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

    def assert_switch_driver_state(self, command, result_state):
        '''
        Transition to a new driver state using command passed.
        @param command: protocol event used to transition state
        @param result_state: final protocol state
        '''
        cmd = AgentCommand(command=command)
        retval = self.instrument_agent_client.execute_resource(cmd)

        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, result_state)

    def test_instrument_agent_common_state_model_lifecycle(self,  timeout=GO_ACTIVE_TIMEOUT):
        """
        @brief Test agent state transitions.
               This test verifies that the instrument agent can
               properly command the instrument through the following states.
        @todo  Once direct access settles down and works again, re-enable direct access.

                COMMANDS TESTED
                *ResourceAgentEvent.INITIALIZE
                *ResourceAgentEvent.RESET
                *ResourceAgentEvent.GO_ACTIVE
                *ResourceAgentEvent.RUN
                *ResourceAgentEvent.PAUSE
                *ResourceAgentEvent.RESUME
                *ResourceAgentEvent.GO_COMMAND
                *ResourceAgentEvent.GO_DIRECT_ACCESS
                *ResourceAgentEvent.GO_INACTIVE
                *ResourceAgentEvent.PING_RESOURCE
                *ResourceAgentEvent.CLEAR

                COMMANDS NOT TESTED
                * ResourceAgentEvent.GET_RESOURCE_STATE
                * ResourceAgentEvent.GET_RESOURCE
                * ResourceAgentEvent.SET_RESOURCE
                * ResourceAgentEvent.EXECUTE_RESOURCE

                STATES ACHIEVED:
                * ResourceAgentState.UNINITIALIZED
                * ResourceAgentState.INACTIVE
                * ResourceAgentState.IDLE'
                * ResourceAgentState.STOPPED
                * ResourceAgentState.COMMAND
                * ResourceAgentState.DIRECT_ACCESS

                STATES NOT ACHIEVED:
                * ResourceAgentState.STREAMING
                * ResourceAgentState.TEST
                * ResourceAgentState.CALIBRATE
                * ResourceAgentState.BUSY
                -- Not tested because they may not be implemented in the driver
        """
        ####
        # UNINITIALIZED
        ####
        self.assert_agent_state(ResourceAgentState.UNINITIALIZED)

        # Try to run some commands that aren't available in this state
        self.assert_agent_command_exception(ResourceAgentEvent.RUN, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_ACTIVE, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_DIRECT_ACCESS, exception_class=Conflict)

        ####
        # INACTIVE
        ####
        self.assert_agent_command(ResourceAgentEvent.INITIALIZE)
        self.assert_agent_state(ResourceAgentState.INACTIVE)

        # Try to run some commands that aren't available in this state
        self.assert_agent_command_exception(ResourceAgentEvent.RUN, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_DIRECT_ACCESS, exception_class=Conflict)

        ####
        # IDLE
        ####
        self.assert_agent_command(ResourceAgentEvent.GO_ACTIVE)

        # Try to run some commands that aren't available in this state
        self.assert_agent_command_exception(ResourceAgentEvent.INITIALIZE, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_ACTIVE, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.RESUME, exception_class=Conflict)

        # Verify we can go inactive
        self.assert_agent_command(ResourceAgentEvent.GO_INACTIVE)
        self.assert_agent_state(ResourceAgentState.INACTIVE)

        # Get back to idle
        self.assert_agent_command(ResourceAgentEvent.GO_ACTIVE)

        # DIRECT ACCESS
        self.assert_direct_access_start_telnet()
        self.assert_direct_access_stop_telnet()

        # Reset
        self.assert_agent_command(ResourceAgentEvent.RESET)
        self.assert_agent_state(ResourceAgentState.UNINITIALIZED)

    def test_reset(self):
        """
        Verify the agent can be reset
        """
        self.assert_enter_command_mode()
        self.assert_reset()

        self.assert_enter_command_mode()
        self.assert_start_autosample()
        self.assert_reset()

        self.assert_enter_command_mode()
        self.assert_direct_access_start_telnet(timeout=600)
        self.assert_reset()

    @unittest.skip("Transaction management not yet implemented")
    def test_transaction_management_messages(self):
        """
        @brief This tests the start_transaction and
               end_transaction methods.
               https://confluence.oceanobservatories.org/display/syseng/CIAD+MI+SV+Instrument+Agent+Interface#CIADMISVInstrumentAgentInterface-Transactionmanagementmessages
               * start_transaction(acq_timeout,exp_timeout)
               * end_transaction(transaction_id)
               * transaction_id

               See: ion/services/mi/instrument_agent.py
               UPDATE: stub it out fill in later when its available ... place holder
        TODO:
        """
        pass

    def de_dupe(self, list_in):
        unique_set = Set(item for item in list_in)
        return [(item) for item in unique_set]

    @unittest.skip("PROBLEM WITH command=ResourceAgentEvent.GO_ACTIVE")
    def test_driver_notification_messages(self, timeout=GO_ACTIVE_TIMEOUT):
        """
        @brief This tests event messages from the driver.  The following
               test moves the IA through all its states.  As it does this,
               event messages are generated and caught.  These messages
               are then compared with a list of expected messages to
               insure that the proper messages have been generated.
        """

        # Clear off any events from before this test so we have consistent state

        self.event_subscribers.events_received = []

        expected_events = [
            'AgentCommand=RESOURCE_AGENT_EVENT_CLEAR',
            'AgentCommand=RESOURCE_AGENT_EVENT_GO_ACTIVE',
            'AgentCommand=RESOURCE_AGENT_EVENT_GO_COMMAND',
            'AgentCommand=RESOURCE_AGENT_EVENT_GO_DIRECT_ACCESS',
            'AgentCommand=RESOURCE_AGENT_EVENT_INITIALIZE',
            'AgentCommand=RESOURCE_AGENT_EVENT_PAUSE',
            'AgentCommand=RESOURCE_AGENT_EVENT_RESET',
            'AgentCommand=RESOURCE_AGENT_EVENT_RESUME',
            'AgentCommand=RESOURCE_AGENT_EVENT_RUN',
            'AgentCommand=RESOURCE_AGENT_PING_RESOURCE',
            'AgentState=RESOUCE_AGENT_STATE_DIRECT_ACCESS',
            'AgentState=RESOURCE_AGENT_STATE_COMMAND',
            'AgentState=RESOURCE_AGENT_STATE_IDLE',
            'AgentState=RESOURCE_AGENT_STATE_INACTIVE',
            'AgentState=RESOURCE_AGENT_STATE_STOPPED',
            'AgentState=RESOURCE_AGENT_STATE_UNINITIALIZED',
            'ResourceConfig',
            'ResourceState=DRIVER_STATE_COMMAND',
            'ResourceState=DRIVER_STATE_DIRECT_ACCESS',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_UNCONFIGURED',
            'ResourceState=DRIVER_STATE_UNKNOWN'
        ]


        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=GO_ACTIVE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        retval = self.instrument_agent_client.ping_resource()

        retval = self.instrument_agent_client.ping_agent()

        cmd = AgentCommand(command=ResourceAgentEvent.PING_RESOURCE)
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        self.assertTrue("ping from resource ppid" in retval.result)

        #cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        #retval = self.instrument_agent_client.execute_agent(cmd)
        #state = self.instrument_agent_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.IDLE)

        #cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        #retval = self.instrument_agent_client.execute_agent(cmd)
        #state = self.instrument_agent_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=GO_ACTIVE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.PAUSE)
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STOPPED)

        cmd = AgentCommand(command=ResourceAgentEvent.RESUME)
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.CLEAR)
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
            #kwargs={'session_type': DirectAccessTypes.telnet,
            kwargs={'session_type':DirectAccessTypes.vsp,
                    'session_timeout':600,
                    'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        # assert it is as long as expected 4149CB23-AF1D-43DF-8688-DDCD2B8E435E
        self.assertTrue(36 == len(retval.result['token']))

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.DIRECT_ACCESS)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_COMMAND)
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd,
                                                            timeout=EXECUTE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)


        #
        # Refactor changed it so no description is ever present.
        # go with state instead i guess...
        #

        raw_events = []
        for x in self.event_subscribers.events_received:
            if str(type(x)) == "<class 'interface.objects.ResourceAgentCommandEvent'>":
                log.debug(str(type(x)) + " ++********************* AgentCommand=" + str(x.execute_command))
                raw_events.append("AgentCommand=" + str(x.execute_command))
            elif str(type(x)) == "<class 'interface.objects.ResourceAgentResourceStateEvent'>":
                log.debug(str(type(x)) + " ++********************* ResourceState=" + str(x.state))
                raw_events.append("ResourceState=" + str(x.state))
            elif str(type(x)) == "<class 'interface.objects.ResourceAgentStateEvent'>":
                log.debug(str(type(x)) + " ++********************* AgentState=" + str(x.state))
                raw_events.append("AgentState=" + str(x.state))
            elif str(type(x)) == "<class 'interface.objects.ResourceAgentResourceConfigEvent'>":
                log.debug(str(type(x)) + " ++********************* ResourceConfig")
                raw_events.append("ResourceConfig")
            else:
                log.debug(str(type(x)) + " ++********************* " + str(x))

        for x in sorted(raw_events):
            log.debug(str(x) + " ?in (expected_events) = " + str(x in expected_events))
            self.assertTrue(x in expected_events)

        for x in sorted(expected_events):
            log.debug(str(x) + " ?in (raw_events) = " + str(x in raw_events))
            self.assertTrue(x in raw_events)

        # assert we got the expected number of events
        num_expected = len(self.de_dupe(expected_events))
        num_actual = len(self.de_dupe(raw_events))
        log.debug("num_expected = " + str(num_expected) + " num_actual = " + str(num_actual))
        self.assertTrue(num_actual == num_expected)

        pass

    @unittest.skip("Driver.get_device_signature not yet implemented")
    def test_get_device_signature(self):
        """
        @Brief this test will call get_device_signature once that is
               implemented in the driver
        """
        pass


class InstrumentDriverPublicationTestCase(InstrumentDriverTestCase):
    """
    Test driver publication.  These test are not include in general driver
    qualification because publication definitions could change.
    """
    def setUp(self):
        """
        @brief Setup test cases.
        """
        InstrumentDriverTestCase.setUp(self)

        self.init_instrument_simulator()
        self.init_port_agent()

        pa_config = self.port_agent_config()

        # Override some preload values
        config = {
            'idk_agent': self.test_config.instrument_agent_preload_id,
            'idk_comms_method': 'ethernet',
            'idk_server_address': 'localhost',
            'idk_comms_device_address': pa_config.get('device_addr'),
            'idk_comms_device_port': pa_config.get('device_port'),
            'idk_comms_server_address': 'localhost',
            'idk_comms_server_port': pa_config.get('data_port'),
            'idk_comms_server_cmd_port': pa_config.get('command_port'),
        }

        self.instrument_agent_manager = InstrumentAgentClient()
        self.instrument_agent_manager.start_container(deploy_file=self.test_config.publisher_deploy_file, container_config=config)

        self.container = self.instrument_agent_manager.container

        log.debug("Packet Config: %s" % self.test_config.instrument_agent_packet_config)
        self.data_subscribers = InstrumentAgentDataSubscribers(
            packet_config=self.test_config.instrument_agent_packet_config,
            use_default_stream=False
        )
        self.event_subscribers = InstrumentAgentEventSubscribers(instrument_agent_resource_id=self.test_config.instrument_agent_resource_id)

        self.init_instrument_agent_client()

        self.event_subscribers.events_received = []
        self.data_subscribers.start_data_subscribers()

        log.debug("********* setUp complete.  Begin Testing *********")

    def tearDown(self):
        """
        @brief Test teardown
        """
        log.debug("InstrumentDriverQualificationTestCase tearDown")

        self.assert_reset()
        self.instrument_agent_manager.stop_container()
        self.event_subscribers.stop()
        self.data_subscribers.stop_data_subscribers()
        InstrumentDriverTestCase.tearDown(self)

    def init_instrument_simulator(self):
        """
        Startup a TCP server that we can use as an instrument simulator
        """
        self._instrument_simulator = TCPSimulatorServer()
        self.addCleanup(self._instrument_simulator.close)

        # Wait for the simulator to bind to a port
        timeout = time.time() + 10
        while(timeout > time.time()):
            if(self._instrument_simulator.port > 0):
                log.debug("Instrument simulator initialized on port %s" % self._instrument_simulator.port)
                return

            log.debug("waiting for simulator to bind. sleeping")
            time.sleep(1)

        raise IDKException("Timeout waiting for simulator to bind")

    def port_agent_config(self):
        """
        Overload the default port agent configuration so that
        it connects to a simulated TCP connection.
        """
        comm_config = self.get_comm_config()

        config = {
            'device_addr' : comm_config.device_addr,
            'device_port' : comm_config.device_port,

            'command_port': comm_config.command_port,
            'data_port': comm_config.data_port,

            'process_type': PortAgentProcessType.UNIX,
            'log_level': 5,
        }

        # Override the instrument connection information.
        config['device_addr'] = 'localhost'
        config['device_port'] = self._instrument_simulator.port

        return config

    def init_instrument_agent_client(self):
        log.info("Start Instrument Agent Client")

        # Driver config
        driver_config = {
            'dvr_mod' : self.test_config.driver_module,
            'dvr_cls' : self.test_config.driver_class,
            'workdir' : self.test_config.working_dir,
            'process_type' : (self.test_config.driver_process_type,),
            'comms_config' : self.port_agent_comm_config(),

            'startup_config' : self.test_config.driver_startup_config
        }

        # Create agent config.
        agent_config = {
            'driver_config' : driver_config,
            'stream_config' : self.data_subscribers.stream_config,
            'agent'         : {'resource_id': self.test_config.instrument_agent_resource_id},
            'test_mode' : True  ## Enable a poison pill. If the spawning process dies
            ## shutdown the daemon process.
        }

        # Start instrument agent client.
        self.instrument_agent_manager.start_client(
            name=self.test_config.instrument_agent_name,
            module=self.test_config.data_instrument_agent_module,
            cls=self.test_config.data_instrument_agent_class,
            config=agent_config,
            resource_id=self.test_config.instrument_agent_resource_id,
            deploy_file=self.test_config.container_deploy_file
        )

        self.instrument_agent_client = self.instrument_agent_manager.instrument_agent_client

    def assert_initialize_driver(self, timeout=GO_ACTIVE_TIMEOUT):
        '''
        Walk through IA states to get to command mode from uninitialized
        '''
        state = self.instrument_agent_client.get_agent_state()

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=timeout)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)
        log.info("Sent INITIALIZE; IA state = %s", state)

        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, DriverConnectionState.UNCONFIGURED)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=timeout)
        state = self.instrument_agent_client.get_agent_state()
        log.info("Sent GO_ACTIVE; IA state = %s", state)
        self.assertEqual(state, ResourceAgentState.COMMAND)

    def assert_sample_async(self, data, sampleDataAssert, sampleQueue, timeout=GO_ACTIVE_TIMEOUT):
        """
        force a sample into the port agent and watch a queue for a
        data granule.
        """
        self.data_subscribers.clear_sample_queue(sampleQueue)
        self._instrument_simulator.send(data)
        log.debug("Simulating instrument input: %s" % data)

        samples = self.data_subscribers.get_samples(sampleQueue, timeout=timeout)
        self.assertGreaterEqual(len(samples), 1)
        sample = samples.pop()

        log.debug("SAMPLE: %s" % sample)
        sampleDataAssert(sample)

    def assert_reset(self):
        '''
        Exist active state
        '''
        log.debug("Reset Agent Now!")

        state = self.instrument_agent_client.get_agent_state()
        log.debug("Current State: %s" % state)

        # If in DA mode walk it out
        if(state == ResourceAgentState.DIRECT_ACCESS):
            cmd = AgentCommand(command=ResourceAgentEvent.GO_COMMAND)
            retval = self.instrument_agent_client.execute_agent(cmd, timeout=30)

        # reset the instrument if it has been initialized
        if(state != ResourceAgentState.UNINITIALIZED):
            cmd = AgentCommand(command=ResourceAgentEvent.RESET)
            state = self.instrument_agent_client.get_agent_state()
            self.assertEqual(state, ResourceAgentState.UNINITIALIZED)
