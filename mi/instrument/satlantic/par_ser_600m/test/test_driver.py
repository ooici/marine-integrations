#!/usr/bin/env python

"""
@file ion/services/mi/drivers/satlantic_par/test/test_satlantic_par.py
@author Steve Foley, Ronald Ronquillo
@test ion.services.mi.drivers.satlantic_par
Unit test suite to test Satlantic PAR sensor
@todo Find a way to test timeouts?
"""

from gevent import monkey
monkey.patch_all()

import unittest

from mi.core.unit_test import MiTestCase
import time
import json
import random
from nose.plugins.attrib import attr
from pyon.agent.agent import ResourceAgentState

from mi.core.log import get_logger
log = get_logger()

from mi.core.instrument.instrument_driver import DriverConnectionState, DriverEvent, DriverProtocolState
from mi.core.instrument.instrument_driver import ConfigMetadataKey
from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.protocol_cmd_dict import CommandDictKey
from mi.core.instrument.protocol_param_dict import ParameterDictKey

from mi.idk.unit_test import DriverTestMixin, ParameterTestConfigKey

from mi.core.exceptions import InstrumentDataException, InstrumentCommandException, InstrumentStateException
from mi.core.exceptions import InstrumentParameterException, SampleException

from mi.idk.unit_test import InstrumentDriverUnitTestCase, InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase, AgentCapabilityType

from mi.instrument.satlantic.par_ser_600m.driver import Command, DataParticleType, SatlanticPARInstrumentProtocol
from mi.instrument.satlantic.par_ser_600m.driver import PARProtocolState, PARProtocolEvent, PARCapability, Parameter
from mi.instrument.satlantic.par_ser_600m.driver import ScheduledJob
from mi.instrument.satlantic.par_ser_600m.driver import SatlanticChecksumDecorator, SatlanticPARDataParticle
from mi.instrument.satlantic.par_ser_600m.driver import SatlanticPARDataParticleKey, SatlanticPARInstrumentDriver

VALID_SAMPLE = "SATPAR0229,10.01,2206748544,234\r\n"
# Make tests verbose and provide stdout
# bin/nosetests -s -v ion/services/mi/drivers/test/test_satlantic_par.py
# All unit tests: add "-a UNIT" to end, integration add "-a INT"
# Test device is at 10.180.80.173, port 2001

# these values checkout against the sample above
valid_particle = [{DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.SERIAL_NUM, DataParticleKey.VALUE: 229},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.TIMER, DataParticleKey.VALUE: 10.01},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.COUNTS, DataParticleKey.VALUE: 2206748544},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.CHECKSUM, DataParticleKey.VALUE: 234}]

VALID_HEADER = "Satlantic Digital PAR Sensor\r\n" + \
               "Copyright (C) 2003, Satlantic Inc. All rights reserved.\r\n" + \
               "Instrument: SATPAR\r\n" + \
               "S/N: 0226\r\n" + \
               "Firmware: 1.0.0\r\n"
VALID_FIRMWARE = "1.0.0"
VALID_SERIAL = "0226"
VALID_INSTRUMENT = "SATPAR"

TIMEOUT = 30


class PARMixin(DriverTestMixin):
    """
    Mixin class used for storing data particle constance and common data assertion methods.
    """
    # Create some short names for the parameter test config
    TYPE      = ParameterTestConfigKey.TYPE
    READONLY  = ParameterTestConfigKey.READONLY
    STARTUP   = ParameterTestConfigKey.STARTUP
    DA        = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE     = ParameterTestConfigKey.VALUE
    REQUIRED  = ParameterTestConfigKey.REQUIRED
    DEFAULT   = ParameterTestConfigKey.DEFAULT

    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.MAXRATE: {TYPE: bool, READONLY: False, DA: True, STARTUP: True, VALUE: 2},
        Parameter.FIRMWARE: {TYPE: bool, READONLY: True, DA: False, STARTUP: False, VALUE: '1.0.0'},
        Parameter.SERIAL: {TYPE: bool, READONLY: True, DA: False, STARTUP: False, VALUE: 229},
        Parameter.INSTRUMENT: {TYPE: bool, READONLY: True, DA: False, STARTUP: False, VALUE: 'SATPAR'},
    }

    _sample_parameters = {
        SatlanticPARDataParticleKey.SERIAL_NUM: {TYPE: int, VALUE: 229, REQUIRED: True},
        SatlanticPARDataParticleKey.COUNTS: {TYPE: int, VALUE: 2206748544, REQUIRED: True},
        SatlanticPARDataParticleKey.TIMER: {TYPE: float, VALUE: 10.01, REQUIRED: True},
        SatlanticPARDataParticleKey.CHECKSUM: {TYPE: int, VALUE: 234, REQUIRED: True},
    }

    ###
    #   Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values=False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    def assert_particle_sample(self, data_particle, verify_values=False):
        """
        Verify sample particle
        @param data_particle:  SBE16DataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(SatlanticPARDataParticleKey, self._sample_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.PARSED)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)


@attr('UNIT', group='mi')
class SatlanticParProtocolUnitTest(InstrumentDriverUnitTestCase, PARMixin):
    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(Command())
        self.assert_enum_has_no_duplicates(ScheduledJob())
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(PARProtocolState())
        self.assert_enum_has_no_duplicates(PARProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())

        # Test capabilites for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(PARCapability())
        self.assert_enum_complete(PARCapability(), PARProtocolEvent())

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = SatlanticPARInstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, VALID_SAMPLE, self.assert_particle_sample, True)

    def test_extract_header(self):
        """
        Test if we can extract the firmware, serial number and instrument label
        from the header.
        """
        def event_callback(event):
            pass

        protocol = SatlanticPARInstrumentProtocol(event_callback)
        protocol._extract_header(VALID_HEADER)

        self.assertEqual(protocol._firmware, VALID_FIRMWARE)
        self.assertEqual(protocol._serial, VALID_SERIAL)
        self.assertEqual(protocol._instrument, VALID_INSTRUMENT)

    def test_sample_format(self):
        """
        Verify driver can get sample data out in a reasonable format.
        Parsed is all we care about...raw is tested in the base DataParticle tests
        """

        port_timestamp = 3555423720.711772
        driver_timestamp = 3555423722.711772

        # construct the expected particle
        expected_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: DataParticleType.PARSED,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: valid_particle
        }

        self.compare_parsed_data_particle(SatlanticPARDataParticle,
                                          VALID_SAMPLE,
                                          expected_particle)

    def test_chunker(self):
        """
        Tests the chunker
        """
        # This will want to be created in the driver eventually...
        chunker = StringChunker(SatlanticPARInstrumentProtocol.sieve_function)

        self.assert_chunker_sample(chunker, VALID_SAMPLE)
        self.assert_chunker_sample(chunker, VALID_HEADER)

        self.assert_chunker_fragmented_sample(chunker, VALID_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, VALID_HEADER)

        self.assert_chunker_combined_sample(chunker, VALID_SAMPLE)
        self.assert_chunker_combined_sample(chunker, VALID_HEADER)

        self.assert_chunker_sample_with_noise(chunker, VALID_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, VALID_HEADER)

    def test_corrupt_data_structures(self):
        """
        Verify when generating the particle, if the particle is corrupt, an exception is raised
        """

        log.debug('test_corrupt_data_structures: %s', VALID_SAMPLE.replace('A', 'B'))
        particle = SatlanticPARDataParticle(VALID_SAMPLE.replace('A', 'B'), port_timestamp=3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()


@attr('INT', group='mi')
class SatlanticParProtocolIntegrationTest(InstrumentDriverIntegrationTestCase, PARMixin):

    def check_state(self, expected_state):
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, expected_state)

    def put_instrument_in_command_mode(self):
        """Wrap the steps and asserts for going into command mode.
           May be used in multiple test cases.
        """
        # Test that the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Setup the protocol state machine and the connection to port agent.
        self.driver_client.cmd_dvr('connect')

        # Test that the driver protocol is in state unknown.
        self.check_state(PARProtocolState.UNKNOWN)

        # Discover what state the instrument is in and set the protocol state accordingly.
        self.driver_client.cmd_dvr('discover_state')

        # Test that the driver protocol is in state command.
        self.check_state(PARProtocolState.COMMAND)

    @unittest.skip('temp disable')
    def test_startup_configuration(self):
        """
        Test that the startup configuration is applied correctly
        """
        self.assert_initialize_driver()

        result = self.driver_client.cmd_dvr('apply_startup_params')

        reply = self.driver_client.cmd_dvr('get_resource', [Parameter.MAXRATE])

        self.assertEquals(reply, {Parameter.MAXRATE: 2})

        reply = self.driver_client.cmd_dvr('set_resource', {Parameter.MAXRATE: 1})

    @unittest.skip('temp disable')
    def test_configuration(self):
        """
        Test to configure the driver process for device comms and transition
        to disconnected state.
        """

        # Test that the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Re-Initialize the driver and transition to unconfigured.
        self.driver_client.cmd_dvr('initialize')

        # Test that the driver returned to state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

    def test_connect_disconnect(self):
        """
        Test configuring and connecting to the device through the port
        agent. Discover device state.  Then disconnect and re-initialize
        """
        self.assert_initialize_driver()

        # Stop comms and transition to disconnected.
        self.driver_client.cmd_dvr('disconnect')

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Re-Initialize the driver and transition to unconfigured.
        self.driver_client.cmd_dvr('initialize')
    
        # Test that the driver returned to state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)
        
    @unittest.skip('temp disable')
    def test_get(self):
        
        self.put_instrument_in_command_mode()

        params = {
                    Parameter.MAXRATE: 1,
                    Parameter.FIRMWARE: "1.0.0",
                    Parameter.SERIAL: "0226",
                    Parameter.INSTRUMENT: "SATPAR"
        }

        reply = self.driver_client.cmd_dvr('get_resource',
                                           params.keys(),
                                           timeout=20)
        
        # self.assertEquals(reply, params)
        
        # self.assertRaises(InstrumentCommandException, self.driver_client.cmd_dvr, 'bogus', [Parameter.MAXRATE])

        # Assert get fails without a parameter.
        self.assertRaises(InstrumentParameterException, self.driver_client.cmd_dvr, 'get_resource')
            
        # Assert get fails with a bad parameter (not ALL or a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = 'I am a bogus param list.'
            self.driver_client.cmd_dvr('get_resource', bogus_params)
            
        # Assert get fails with a bad parameter in a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = [
                'a bogus parameter name',
                Parameter.MAXRATE
            ]
            self.driver_client.cmd_dvr('get_resource', bogus_params)        
        
    @unittest.skip('temp disable')
    def test_set(self):
        config_key = Parameter.MAXRATE
        value_a = 12
        value_b = 1
        config_a = {config_key: value_a}
        config_b = {config_key: value_b}
        
        self.put_instrument_in_command_mode()
        
        reply = self.driver_client.cmd_dvr('set_resource', config_a, timeout=20)
        self.assertEquals(reply[config_key], value_a)
                 
        reply = self.driver_client.cmd_dvr('get_resource', [config_key], timeout=20)
        self.assertEquals(reply, config_a)
        
        reply = self.driver_client.cmd_dvr('set_resource', config_b, timeout=20)
        self.assertEquals(reply[config_key], value_b)
         
        reply = self.driver_client.cmd_dvr('get_resource', [config_key], timeout=20)
        self.assertEquals(reply, config_b)

        # Assert we cannot set a bogus parameter.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                'a bogus parameter name': 'bogus value'
            }
            self.driver_client.cmd_dvr('set_resource', bogus_params)
            
        # Assert we cannot set a real parameter to a bogus value.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                Parameter.MAXRATE: 'bogus value'
            }
            self.driver_client.cmd_dvr('set_resource', bogus_params)

    @unittest.skip('temp disable')
    def test_set_init_params(self):
        """
        Verify the instrument will set the init params from a config file
        This verifies setting all the parameters.
        """
        self.assert_initialize_driver()

        values_before = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        log.debug("VALUES_BEFORE = %s", values_before)
        # self.assertEquals(values_before[Parameter.MEASUREMENT_INTERVAL], 1)
        # self.assertEquals(values_before[Parameter.NUMBER_SAMPLES_PER_BURST], 0)

        self.driver_client.cmd_dvr('set_init_params',
                                   {DriverConfigKey.PARAMETERS:
                                       {DriverParameter.ALL:
                                        base64.b64encode(user_config1())}})

        values_after = self.driver_client.cmd_dvr("get_resource", Parameter.ALL)
        log.debug("VALUES_AFTER = %s", values_after)

        self.assertEquals(values_after[Parameter.TRANSMIT_PULSE_LENGTH], 2)
        self.assertEquals(values_after[Parameter.BLANKING_DISTANCE], 16)

    # @unittest.skip('temp disable')
    def test_parameters(self):
        """
        Verify that we can set the parameters

        1. Cannot set read only parameters
        2. Can set read/write parameters
        3. Can set read/write parameters w/direct access only
        """
        self.assert_initialize_driver(PARProtocolState.COMMAND)

        #test read/write parameter
        self.assert_set(Parameter.MAXRATE, 2, no_get=True)

        #test read only parameter
        # self.assert_set_exception(Parameter.USER_4_SPARE, 'blah', exception_class=InstrumentParameterException)

    def test_metadata_generation(self):
        """
        Verify the driver generates metadata information
        """
        self.assert_initialize_driver()

        self.assert_metadata_generation(instrument_params=Parameter.list(), commands=PARCapability.list())

        # check one to see that the file is loading data from somewhere.
        json_result = self.driver_client.cmd_dvr("get_config_metadata")
        result = json.loads(json_result)

        params = result[ConfigMetadataKey.PARAMETERS]
        self.assertEqual(params[Parameter.MAXRATE][ParameterDictKey.DISPLAY_NAME], "MaxRate")

        cmds = result[ConfigMetadataKey.COMMANDS]
        self.assertEqual(cmds[PARCapability.ACQUIRE_SAMPLE][CommandDictKey.DISPLAY_NAME], "Acquire Sample")

    # @unittest.skip('temp disable')
    def test_acquire_sample(self):
        """
        Test acquire sample command and events.

        1. initialize the instrument to COMMAND state
        2. command the instrument to ACQUIRE SAMPLE
        3. verify the particle coming in
        """
        self.assert_initialize_driver(PARProtocolState.COMMAND)
        self.assert_driver_command(PARProtocolEvent.ACQUIRE_SAMPLE, state=PARProtocolState.COMMAND, delay=1)
        self.assert_async_particle_generation(DataParticleType.PARSED, self.assert_particle_sample)

    def test_command_autosample(self):
        """
        Test autosample command and events.

        1. initialize the instrument to COMMAND state
        2. command the instrument to AUTOSAMPLE
        3. verify the particle coming in
        4. command the instrument back to COMMAND state
        """
        timeout = 2*60
        count = 0
        starttime = time.time()
        startstamp = time.strftime("%H:%M:%S", time.gmtime())
        maxrates = [[0,1], [0.125,9], [0.5,3], [1,2], [2,1], [4,1], [8,1], [10,1], [12,1]]
        maxrates = [[0,1], [0.125,9], [0.5,3], [1,2], [2,1], [4,1], [8,1], [10,1], [12,1]]

        self.assert_initialize_driver(PARProtocolState.COMMAND)

        while True:
            random.shuffle(maxrates)
            for maxrate, min_sleep in maxrates:
                sleep_time = random.uniform(min_sleep, 15)
                count +=1
                log.debug('START test_command_autosample: #%s maxrate=%s, %s, sleep=%s', count, maxrate, time.strftime("%H:%M:%S", time.gmtime()), sleep_time)
                self.assert_set(Parameter.MAXRATE, maxrate, no_get=True)
                self.assert_driver_command(PARProtocolEvent.START_AUTOSAMPLE, state=PARProtocolState.AUTOSAMPLE, delay=3)
                time.sleep(sleep_time)
                self.assert_async_particle_generation(DataParticleType.PARSED, self.assert_particle_sample)
                self.assert_driver_command(PARProtocolEvent.STOP_AUTOSAMPLE, state=PARProtocolState.COMMAND, delay=3)
            if time.time() > starttime + timeout:
                break

        self.assert_set(Parameter.MAXRATE, 4, no_get=True)
        log.debug('FINISHED test_command_autosample: #%s, start:%s/end:%s, timeout=%s', count, startstamp, time.strftime("%H:%M:%S", time.gmtime()), timeout)

    def test_direct_access(self):
        """
        Verify the driver can enter/exit the direct access state
        """
        self.assert_initialize_driver(PARProtocolState.COMMAND)

        self.assert_driver_command(PARProtocolEvent.START_DIRECT, state=PARProtocolState.DIRECT_ACCESS, delay=1)

        # TODO: add test to change stuff? or is that covered by QUAL?

        self.assert_driver_command(PARProtocolEvent.STOP_DIRECT, state=PARProtocolState.COMMAND, delay=1)

        # self.assert_initialize_driver(PARProtocolState.COMMAND)
        # self.assert_state_change(PARProtocolState.COMMAND, 5)
        # log.debug('in command mode')
        #
        # self.driver_client.cmd_dvr('execute_resource', PARProtocolState.START_DIRECT)
        # self.assert_state_change(PARProtocolState.v, 5)
        # log.debug('in direct access')
        #
        # self.driver_client.cmd_dvr('execute_resource', PARProtocolState.STOP_DIRECT)
        # self.assert_state_change(PARProtocolState.COMMAND, 5)
        # log.debug('leaving direct access')

    def test_errors(self):
        """
        Verify response to erroneous commands and setting bad parameters.
        """
        self.assert_initialize_driver(PARProtocolState.COMMAND)

        #Assert an invalid command
        # self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

        # Assert for a known command, invalid state.
        self.assert_driver_command_exception(PARProtocolEvent.STOP_AUTOSAMPLE,
                                             exception_class=InstrumentCommandException)

        # Assert set fails with a bad parameter (not ALL or a list).
        self.assert_set_exception('I am a bogus param.', exception_class=InstrumentParameterException)

        #Assert set fails with bad parameter and bad value
        self.assert_set_exception('I am a bogus param.', value='bogus value',
                                  exception_class=InstrumentParameterException)

        # put driver in disconnected state.
        self.driver_client.cmd_dvr('disconnect')

        # Assert for a known command, invalid state.
        self.assert_driver_command_exception(PARProtocolEvent.START_POLL, exception_class=InstrumentCommandException)

        # Test that the driver is in state disconnected.
        self.assert_state_change(DriverConnectionState.DISCONNECTED, timeout=TIMEOUT)

        # Setup the protocol state machine and the connection to port agent.
        self.driver_client.cmd_dvr('initialize')

        # Test that the driver is in state unconfigured.
        self.assert_state_change(DriverConnectionState.UNCONFIGURED, timeout=TIMEOUT)

        # Assert we forgot the comms parameter.
        self.assert_driver_command_exception('configure', exception_class=InstrumentParameterException)

        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.assert_state_change(DriverConnectionState.DISCONNECTED, timeout=TIMEOUT)

    @unittest.skip('temp disable')
    #@unittest.skip('temp for debugging')
    def test_error_conditions(self):
        # Test that the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Assert we forgot the comms parameter.
        self.assertRaises(InstrumentParameterException,
                          self.driver_client.cmd_dvr, 'configure')

        # Assert we send a bad config object (not a dict).
        with self.assertRaises(InstrumentParameterException):
            bogus_config = 'not a config dict'
            self.driver_client.cmd_dvr('configure', bogus_config)
            
        # Assert we send a bad config object (missing addr value).
        with self.assertRaises(InstrumentParameterException):
            bogus_config = self.port_agent_comm_config().copy()
            bogus_config.pop('addr')
            self.driver_client.cmd_dvr('configure', bogus_config)

        # Assert we send a bad config object (bad addr value).
        with self.assertRaises(InstrumentParameterException):
            bogus_config = self.port_agent_comm_config().copy()
            bogus_config['addr'] = ''
            self.driver_client.cmd_dvr('configure', bogus_config)
        
        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Assert for a known command, invalid state.
        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.ACQUIRE_SAMPLE)

        # Setup the protocol state machine and the connection to port agent.
        self.driver_client.cmd_dvr('connect')

        # Test that the driver protocol is in state unknown.
        self.check_state(PARProtocolState.UNKNOWN)

        # Assert for a known command, invalid state.
        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.ACQUIRE_SAMPLE)

        # Discover what state the instrument is in and set the protocol state accordingly.
        self.driver_client.cmd_dvr('discover_state')

        # Test that the driver protocol is in state command.
        self.check_state(PARProtocolState.COMMAND)

        # tests when driver is in command mode
        # Test a bad driver command 
        self.assertRaises(InstrumentCommandException, 
                          self.driver_client.cmd_dvr, 'bogus_command')
        
        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr, 'connect')

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.ACQUIRE_SAMPLE)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.RESET)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_AUTOSAMPLE)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_POLL)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.EXECUTE_DIRECT)

        # tests when driver is in auto-sample mode
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.START_AUTOSAMPLE)
        self.check_state(PARProtocolState.AUTOSAMPLE)

        # Test a bad driver command 
        self.assertRaises(InstrumentCommandException, 
                          self.driver_client.cmd_dvr, 'bogus_command')
        
        # Test get from wrong state
        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'get_resource', [Parameter.MAXRATE])

        # Test set from wrong state
        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr, 'set_resource', {Parameter.MAXRATE: 10})

        # test commands for invalid state
        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.ACQUIRE_SAMPLE)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.START_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.EXECUTE_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_POLL)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.START_AUTOSAMPLE)

        # tests when driver is in poll mode
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.START_POLL)
        self.check_state(PARProtocolState.POLL)

        # Test a bad driver command 
        self.assertRaises(InstrumentCommandException, 
                          self.driver_client.cmd_dvr, 'bogus_command')
        
        # Test get from wrong state
        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'get_resource', [Parameter.MAXRATE])

        # Test set from wrong state
        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr, 'set_resource', {Parameter.MAXRATE: 10})

        # test commands for invalid state
        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.START_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.EXECUTE_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_AUTOSAMPLE)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.START_POLL)

    @unittest.skip('temp disable')
    def test_stop_from_slow_autosample(self):
        # test break from autosample at low data rates
        self.put_instrument_in_command_mode()
        
        self.driver_client.cmd_dvr('set_resource', {Parameter.MAXRATE: 1}, timeout=20)

        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.START_AUTOSAMPLE)
        #time.sleep(5)
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.STOP_AUTOSAMPLE)
        self.check_state(PARProtocolState.COMMAND)

    @unittest.skip('temp disable')
    def test_stop_from_fast_autosample(self):
        # test break from autosample at high data rates
        self.put_instrument_in_command_mode()
        
        self.driver_client.cmd_dvr('set_resource', {Parameter.MAXRATE: 12}, timeout=20)

        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.START_AUTOSAMPLE)
        #time.sleep(5)
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.STOP_AUTOSAMPLE)
        self.check_state(PARProtocolState.COMMAND)
        self.driver_client.cmd_dvr('set_resource', {Parameter.MAXRATE: 1}, timeout=20)


    @unittest.skip('temp disable')
    def test_start_stop_poll(self):
        self.put_instrument_in_command_mode()
        
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.START_POLL)
        self.check_state(PARProtocolState.POLL)
        time.sleep(2)

        # Already in poll mode, so this shouldn't give us anything
        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.START_POLL)
        
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.ACQUIRE_SAMPLE)

        # @todo check samples arriving here
        # @todo check publishing samples from here
        
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.STOP_POLL)        
        self.check_state(PARProtocolState.COMMAND)

    @unittest.skip('Need to write this test')
    def test_reset(self):
        pass


@attr('UNIT', group='mi')
class SatlanticParDecoratorTest(MiTestCase):
    
    def setUp(self):
        self.checksum_decorator = SatlanticChecksumDecorator()

    @unittest.skip("Needs to be revisited.  Is this used?")
    def test_checksum(self):
        self.assertEquals(("SATPAR0229,10.01,2206748544,234","SATPAR0229,10.01,2206748544,234"),
                          self.checksum_decorator.handle_incoming_data("SATPAR0229,10.01,2206748544,234",
                                                                       "SATPAR0229,10.01,2206748544,234"))
        self.assertRaises(InstrumentDataException,
                          self.checksum_decorator.handle_incoming_data,
                          "SATPAR0229,10.01,2206748544,235",
                          "SATPAR0229,10.01,2206748544,235")


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class SatlanticParProtocolQualificationTest(InstrumentDriverQualificationTestCase, PARMixin):
    """Qualification Test Container"""
    
    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.  

    def assertSampleDataParticle(self, val):
        """
        Verify the value for a par sample data particle

        {
          'quality_flag': 'ok',
          'preferred_timestamp': 'driver_timestamp',
          'stream_name': 'parsed',
          'pkt_format_id': 'JSON_Data',
          'pkt_version': 1,
          'driver_timestamp': 3559843883.8029947,
          'values': [
            {'value_id': 'serial_num', 'value': '0226'},
            {'value_id': 'elapsed_time', 'value': 7.17},
            {'value_id': 'counts', 'value': 2157033280},
            {'value_id': 'checksum', 'value': 27}
          ],
        }
        """

        if isinstance(val, SatlanticPARDataParticle):
            sample_dict = json.loads(val.generate())
        else:
            sample_dict = val

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME], DataParticleType.PARSED)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID], DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES], list))
        self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        for x in sample_dict['values']:
            self.assertTrue(x['value_id'] in ['serial_num', 'elapsed_time', 'counts', 'checksum'])
            log.debug("ID: %s value: %s type: %s" % (x['value_id'], x['value'], type(x['value'])))
            if x['value_id'] == 'elapsed_time':
                self.assertTrue(isinstance(x['value'], float))
            elif x['value_id'] == 'serial_num':
                self.assertTrue(isinstance(x['value'], str))
            elif x['value_id'] == 'counts':
                self.assertTrue(isinstance(x['value'], int))
            elif x['value_id'] == 'checksum':
                self.assertTrue(isinstance(x['value'], int))
            else:
                # Shouldn't get here.  If we have then we aren't checking a parameter
                self.assertFalse(True)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly
        supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data("\r\n")
        self.tcp_client.expect("Invalid command")

        self.assert_direct_access_stop_telnet()

    @unittest.skip("polled mode note implemented")
    def test_poll(self):
        """
        No polling for a single sample
        """

        #self.assert_sample_polled(self.assertSampleDataParticle,
        #                          DataParticleValue.PARSED)

    def test_autosample(self):
        """
        start and stop autosample and verify data particle
        """
        self.assert_sample_autosample(self.assertSampleDataParticle, DataParticleValue.PARSED)

    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly
        """
        self.assert_enter_command_mode()

        self.assert_set_parameter(Parameter.MAXRATE, 4)
        self.assert_set_parameter(Parameter.MAXRATE, 1)

        self.assert_get_parameter(Parameter.FIRMWARE, "1.0.0")
        self.assert_get_parameter(Parameter.SERIAL, "0226")
        self.assert_get_parameter(Parameter.INSTRUMENT, "SATPAR")

        self.assert_reset()

    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################

        capabilities = {}
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.COMMAND)
        capabilities[AgentCapabilityType.AGENT_PARAMETER] = self._common_agent_parameters()
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [PARProtocolEvent.ACQUIRE_SAMPLE,
                                                               PARProtocolEvent.GET,
                                                               PARProtocolEvent.SET,    # TODO: add all of them!
                                                               PARProtocolEvent.ACQUIRE_STATUS,
                                                               PARProtocolEvent.START_AUTOSAMPLE,
                                                               PARProtocolEvent.START_DIRECT,
                                                               PARProtocolEvent.STOP_AUTOSAMPLE,
                                                               PARProtocolEvent.START_POLL]
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = None
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = self._driver_parameters.keys()

        self.assert_enter_command_mode()
        self.assert_capabilities(capabilities)

        ##################
        #  Polled Mode
        ##################
        capabilities = {}
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [PARProtocolEvent.START_AUTOSAMPLE,
                                                              PARProtocolEvent.RESET,
                                                              PARProtocolEvent.STOP_POLL]
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = self._driver_parameters.keys()

        self.assert_switch_driver_state(PARProtocolEvent.START_POLL, DriverProtocolState.POLL)
        self.assert_capabilities(capabilities)
        self.assert_switch_driver_state(PARProtocolEvent.STOP_POLL, DriverProtocolState.COMMAND)

        ##################
        #  Streaming Mode
        ##################
        capabilities = {} # TODO: this needed?
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [PARProtocolEvent.START_POLL,
                                                              PARProtocolEvent.STOP_AUTOSAMPLE]
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = self._driver_parameters.keys()

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        # ##################
        # #  DA Mode
        # ##################
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [PARProtocolEvent.STOP_DIRECT]

        self.assert_direct_access_start_telnet()
        self.assert_capabilities(capabilities)
        self.assert_direct_access_stop_telnet()

        #######################
        #  Uninitialized Mode
        #######################
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.UNINITIALIZED)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)