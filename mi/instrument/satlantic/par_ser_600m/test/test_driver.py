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
from mock import Mock
from pyon.agent.agent import ResourceAgentState

from interface.objects import AgentCommand

from mi.core.log import get_logger
log = get_logger()

from mi.core.instrument.instrument_driver import DriverConnectionState, DriverEvent, DriverProtocolState
from mi.core.instrument.instrument_driver import ConfigMetadataKey, DriverConfigKey
from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.protocol_cmd_dict import CommandDictKey
from mi.core.instrument.protocol_param_dict import ParameterDictKey, ParameterDictType, ParameterDictVisibility

from mi.idk.unit_test import DriverTestMixin, ParameterTestConfigKey, InstrumentDriverTestCase

from mi.core.exceptions import InstrumentDataException, InstrumentCommandException, InstrumentStateException
from mi.core.exceptions import InstrumentParameterException, SampleException

from mi.idk.unit_test import InstrumentDriverUnitTestCase, InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase, AgentCapabilityType

from mi.instrument.satlantic.par_ser_600m.driver import Command, DataParticleType, SatlanticPARInstrumentProtocol
from mi.instrument.satlantic.par_ser_600m.driver import PARProtocolState, PARProtocolEvent, PARCapability, Parameter
from mi.instrument.satlantic.par_ser_600m.driver import ScheduledJob, EOLN, Prompt, SatlanticPARConfigParticle
from mi.instrument.satlantic.par_ser_600m.driver import SatlanticChecksumDecorator, SatlanticPARDataParticle
from mi.instrument.satlantic.par_ser_600m.driver import SatlanticPARDataParticleKey, SatlanticPARConfigParticleKey
from mi.instrument.satlantic.par_ser_600m.driver import SatlanticPARInstrumentDriver, EngineeringParameter
from mi.instrument.satlantic.par_ser_600m.driver import INTERVAL_TIME_REGEX, ParameterUnits


InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.satlantic.par_ser_600m.driver',
    driver_class="SatlanticPARInstrumentDriver",

    instrument_agent_resource_id='satlantic_par_ser_600m_ooicore',
    instrument_agent_name='satlantic_par_ser_600m_agent',
    instrument_agent_packet_config=DataParticleType(),
    driver_startup_config={
        DriverConfigKey.PARAMETERS: {
            Parameter.MAXRATE: 1,
            Parameter.FIRMWARE: ' 1.0.0',
            Parameter.SERIAL: '4278190306',
            Parameter.INSTRUMENT: 'SATPAR'}}
)

VALID_SAMPLE = "SATPAR4278190306,10.01,2206748544,234\r\n"
# Make tests verbose and provide stdout
# bin/nosetests -s -v ion/services/mi/drivers/test/test_satlantic_par.py
# All unit tests: add "-a UNIT" to end, integration add "-a INT"
# Test device is at 10.180.80.173, port 2001

# these values checkout against the sample above
valid_particle = [{DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.SERIAL_NUM, DataParticleKey.VALUE: '4278190306'},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.TIMER, DataParticleKey.VALUE: 10.01},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.COUNTS, DataParticleKey.VALUE: 2206748544},
                  {DataParticleKey.VALUE_ID: SatlanticPARDataParticleKey.CHECKSUM, DataParticleKey.VALUE: 234}]

VALID_HEADER = "Satlantic Digital PAR Sensor\r\n" + \
               "Copyright (C) 2003, Satlantic Inc. All rights reserved.\r\n" + \
               "Instrument: SATPAR\r\n" + \
               "S/N: 4278190306\r\n" + \
               "Firmware: 1.0.0\r\n"

VALID_CONFIG = "Maximum Frame Rate: 0.125 Hz\r\n" + \
               "Telemetry Baud Rate: 19200 bps"

VALID_FIRMWARE = "1.0.0"
VALID_SERIAL = "4278190306"
VALID_INSTRUMENT = "SATPAR"

valid_config_particle = [{DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.BAUD_RATE, DataParticleKey.VALUE: 19200},
                  {DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.MAX_RATE, DataParticleKey.VALUE: 0.125},
                  {DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.SERIAL_NUM, DataParticleKey.VALUE: '4278190306'},
                  {DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.FIRMWARE, DataParticleKey.VALUE: '1.0.0'},
                  {DataParticleKey.VALUE_ID: SatlanticPARConfigParticleKey.TYPE, DataParticleKey.VALUE: 'SATPAR'}]

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
        Parameter.MAXRATE: {TYPE: float, VALUE: 0.5, REQUIRED: True},
        Parameter.FIRMWARE: {TYPE: unicode, VALUE: '1.0.0', REQUIRED: True},
        Parameter.SERIAL: {TYPE: unicode, VALUE: '229', REQUIRED: True},
        Parameter.INSTRUMENT: {TYPE: unicode, VALUE: 'SATPAR', REQUIRED: True},
        Parameter.ACQUIRE_STATUS_INTERVAL: {TYPE: unicode, VALUE: '00:00:00', REQUIRED: True}
    }

    _config_parameters = {
        # Parameters defined in the IOS
        SatlanticPARConfigParticleKey.BAUD_RATE: {TYPE: int, READONLY: True, DA: True, STARTUP: False, VALUE: 19200},
        SatlanticPARConfigParticleKey.MAX_RATE: {TYPE: float, READONLY: False, DA: True, STARTUP: True, VALUE: 0.5},
        SatlanticPARConfigParticleKey.SERIAL_NUM: {TYPE: unicode, READONLY: True, DA: False, STARTUP: False, VALUE: '4278190306'},
        SatlanticPARConfigParticleKey.FIRMWARE: {TYPE: unicode, READONLY: True, DA: False, STARTUP: False, VALUE: '1.0.0'},
        SatlanticPARConfigParticleKey.TYPE: {TYPE: unicode, READONLY: True, DA: False, STARTUP: False, VALUE: 'SATPAR'},
    }

    _sample_parameters = {
        SatlanticPARDataParticleKey.SERIAL_NUM: {TYPE: unicode, VALUE: '4278190306', REQUIRED: True},
        SatlanticPARDataParticleKey.COUNTS: {TYPE: int, VALUE: 2206748544, REQUIRED: True},
        SatlanticPARDataParticleKey.TIMER: {TYPE: float, VALUE: 10.01, REQUIRED: True},
        SatlanticPARDataParticleKey.CHECKSUM: {TYPE: int, VALUE: 234, REQUIRED: True},
    }

    _capabilities = {
        PARProtocolState.UNKNOWN:      [PARProtocolEvent.DISCOVER],

        PARProtocolState.COMMAND:      [PARProtocolEvent.GET,
                                        PARProtocolEvent.SET,
                                        PARProtocolEvent.START_DIRECT,
                                        PARProtocolEvent.START_AUTOSAMPLE,
                                        PARProtocolEvent.ACQUIRE_SAMPLE,
                                        PARProtocolEvent.SCHEDULED_ACQUIRE_STATUS,
                                        PARProtocolEvent.ACQUIRE_STATUS],

        PARProtocolState.AUTOSAMPLE:   [PARProtocolEvent.STOP_AUTOSAMPLE,
                                        PARProtocolEvent.SCHEDULED_ACQUIRE_STATUS,
                                        PARProtocolEvent.RESET],

        PARProtocolState.DIRECT_ACCESS: [PARProtocolEvent.STOP_DIRECT,
                                         PARProtocolEvent.EXECUTE_DIRECT]
    }

    ###
    #   Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values=False):    # TODO rename this!
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        log.debug("assert_driver_parameters")
        self.assert_data_particle_keys(SatlanticPARConfigParticleKey, self._config_parameters)
        self.assert_data_particle_header(current_parameters, DataParticleType.CONFIG)
        self.assert_data_particle_parameters(current_parameters, self._config_parameters, verify_values)

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
        self.assert_enum_has_no_duplicates(Prompt())

        # Test capabilites for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(PARCapability())
        self.assert_enum_complete(PARCapability(), PARProtocolEvent())

    def test_driver_protocol_filter_capabilities(self):
        """
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock(spec="PortAgentClient")
        protocol = SatlanticPARInstrumentProtocol(mock_callback)
        driver_capabilities = PARCapability().list()
        test_capabilities = PARCapability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities), sorted(protocol._filter_capabilities(test_capabilities)))


    def test_chunker(self):
        """
        Tests the chunker
        """
        # This will want to be created in the driver eventually...
        chunker = StringChunker(SatlanticPARInstrumentProtocol.sieve_function)

        self.assert_chunker_sample(chunker, VALID_SAMPLE)
        self.assert_chunker_sample(chunker, VALID_CONFIG)

        self.assert_chunker_fragmented_sample(chunker, VALID_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, VALID_CONFIG)

        self.assert_chunker_combined_sample(chunker, VALID_SAMPLE)
        self.assert_chunker_combined_sample(chunker, VALID_CONFIG)

        self.assert_chunker_sample_with_noise(chunker, VALID_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, VALID_CONFIG)

    def test_corrupt_data_structures(self):
        """
        Verify when generating the particle, if the particle is corrupt, an exception is raised
        """

        log.debug('test_corrupt_data_structures: %s', VALID_SAMPLE.replace('A', 'B'))
        particle = SatlanticPARDataParticle(VALID_SAMPLE.replace('A', 'B'), port_timestamp=3558720820.531179)
        with self.assertRaises(SampleException):
            json_str = particle.generate()
            obj = json.loads(json_str)
            self.assertNotEqual(obj[DataParticleKey.QUALITY_FLAG], DataParticleValue.OK)

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


    def compare_parsed_data_particle_override(self, particle_type, raw_input, happy_structure):
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
            test_particle = particle_type("4278190306", "1.0.0", "SATPAR",
                                          raw_input, port_timestamp=port_timestamp)

        parsed_result = test_particle.generate(sorted=True)
        decoded_parsed = json.loads(parsed_result)

        driver_time = decoded_parsed[DataParticleKey.DRIVER_TIMESTAMP]
        happy_structure[DataParticleKey.DRIVER_TIMESTAMP] = driver_time

        # run it through json so unicode and everything lines up
        standard = json.dumps(happy_structure, sort_keys=True)

        log.debug("Parsed Result:\n%s", json.dumps(json.loads(parsed_result), sort_keys=True, indent=2))
        log.debug("Standard:\n%s", json.dumps(json.loads(standard), sort_keys=True, indent=2))

        self.assertEqual(parsed_result, standard)

    def test_config_format(self):
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
            DataParticleKey.STREAM_NAME: DataParticleType.CONFIG,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: valid_config_particle
        }

        self.compare_parsed_data_particle_override(SatlanticPARConfigParticle,
                                          VALID_CONFIG,
                                          expected_particle)

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """

        driver = SatlanticPARInstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, self._capabilities)

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

    def test_scheduled_clock_sync_acquire_status(self):
        """
        Verify the scheduled clock sync and acquire status is added to the protocol
        Verify if there is no scheduling, nothing is added to the protocol
        """
        mock_callback = Mock(spec="PortAgentClient")
        protocol = SatlanticPARInstrumentProtocol(mock_callback)

        # #Verify there is nothing scheduled
        protocol._handler_autosample_enter()
        self.assertEqual(protocol._scheduler_callback.get(ScheduledJob.ACQUIRE_STATUS), None)

        protocol._param_dict.add(EngineeringParameter.ACQUIRE_STATUS_INTERVAL,
                                   INTERVAL_TIME_REGEX,
                                   lambda match: match.group(1),
                                   str,
                                   type=ParameterDictType.STRING,
                                   visibility=ParameterDictVisibility.IMMUTABLE,
                                   display_name="Acquire Status Interval",
                                   description='Interval for gathering status particles',
                                   units=ParameterUnits.TIME_INTERVAL,
                                   default_value='00:00:02',
                                   startup_param=True)
        # #set the values of the dictionary using set_default
        protocol._param_dict.set_value(EngineeringParameter.ACQUIRE_STATUS_INTERVAL,
                                   protocol._param_dict.get_default_value(EngineeringParameter.ACQUIRE_STATUS_INTERVAL))
        protocol._handler_autosample_enter()

        #Verify there is scheduled events
        self.assertTrue(protocol._scheduler_callback.get(ScheduledJob.ACQUIRE_STATUS))


@attr('INT', group='mi')
class SatlanticParProtocolIntegrationTest(InstrumentDriverIntegrationTestCase, PARMixin):

    def test_parameters(self):
        """
        Verify that we can set the parameters

        1. Cannot set read only parameters
        2. Can set read/write parameters
        """
        self.assert_initialize_driver(PARProtocolState.COMMAND)

        #test read/write parameter
        self.assert_set(Parameter.MAXRATE, 2)

        #test read only parameter
        self.assert_set_exception(Parameter.FIRMWARE, '1.0.1')
        self.assert_set_exception(Parameter.SERIAL, '4278190307')
        self.assert_set_exception(Parameter.INSTRUMENT, 'CATCAR')

    # @unittest.skip('temp disable')
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

    def test_acquire_status(self):
        """
        Test acquire status command and events.

        1. initialize the instrument to COMMAND state
        2. command the instrument to ACQUIRE STATUS
        3. verify the status particle coming in
        """
        self.assert_initialize_driver(PARProtocolState.COMMAND)
        self.assert_driver_command(PARProtocolEvent.ACQUIRE_STATUS, state=PARProtocolState.COMMAND, delay=5)
        self.assert_async_particle_generation(DataParticleType.CONFIG, self.assert_driver_parameters)

    def test_acquire_sample(self):
        """
        Test acquire sample command and events.

        1. initialize the instrument to COMMAND state
        2. command the instrument to ACQUIRE SAMPLE
        3. verify the particle coming in
        """
        self.assert_initialize_driver(PARProtocolState.COMMAND)
        self.assert_driver_command(PARProtocolEvent.ACQUIRE_SAMPLE, state=PARProtocolState.COMMAND, delay=5)
        self.assert_async_particle_generation(DataParticleType.PARSED, self.assert_particle_sample)

    # @unittest.skip('temp disable')
    def test_command_autosample_multiple(self, *args, **kwargs):
        """
        Test autosample command and events.

        1. initialize the instrument to COMMAND state
        2. command the instrument to AUTOSAMPLE
        3. verify the particle coming in
        4. command the instrument back to COMMAND state
        """
        timeout = 25*60
        count = 0
        starttime = time.time()
        startstamp = time.strftime("%H:%M:%S", time.gmtime())
        maxrates = [[0,1], [0.125,9], [0.5,3], [1,2], [2,1], [4,1], [8,1], [10,1], [12,1]]

        self.assert_initialize_driver(PARProtocolState.COMMAND)

        while True:
            random.shuffle(maxrates)
            for maxrate, min_sleep in maxrates:
                sleep_time = random.uniform(min_sleep, 15)
                count +=1
                log.debug('START test_command_autosample: #%s maxrate=%s, %s, sleep=%s', count, maxrate, time.strftime("%H:%M:%S", time.gmtime()), sleep_time)
                self.assert_set(Parameter.MAXRATE, maxrate, no_get=True)

                self.assert_driver_command(PARProtocolEvent.ACQUIRE_STATUS, state=PARProtocolState.COMMAND, delay=5)
                self.assert_async_particle_generation(DataParticleType.CONFIG, self.assert_driver_parameters)

                # self.test_command_autosample(sleep_time=sleep_time)
                self.assert_driver_command(PARProtocolEvent.START_AUTOSAMPLE, state=PARProtocolState.AUTOSAMPLE, delay=3)
                time.sleep(sleep_time)
                self.assert_async_particle_generation(DataParticleType.PARSED, self.assert_particle_sample)
                self.assert_driver_command(PARProtocolEvent.STOP_AUTOSAMPLE, state=PARProtocolState.COMMAND, delay=3)

            if time.time() > starttime + timeout:
                break

        self.assert_set(Parameter.MAXRATE, 4, no_get=True)
        log.debug('FINISHED test_command_autosample: #%s, start:%s/end:%s, timeout=%s', count, startstamp, time.strftime("%H:%M:%S", time.gmtime()), timeout)

    def test_command_autosample(self, sleep_time=15):
        """
        Test autosample command and events.

        1. initialize the instrument to COMMAND state
        2. command the instrument to AUTOSAMPLE
        3. verify the particle coming in
        4. command the instrument back to COMMAND state
        """

        self.assert_initialize_driver(PARProtocolState.COMMAND)
        self.assert_driver_command(PARProtocolEvent.START_AUTOSAMPLE, state=PARProtocolState.AUTOSAMPLE, delay=3)
        time.sleep(sleep_time)
        self.assert_async_particle_generation(DataParticleType.PARSED, self.assert_particle_sample)
        self.assert_driver_command(PARProtocolEvent.STOP_AUTOSAMPLE, state=PARProtocolState.COMMAND, delay=3)

    def test_direct_access(self):
        """
        Verify the driver can enter/exit the direct access state
        """
        self.assert_initialize_driver(PARProtocolState.COMMAND)

        self.assert_state_change(PARProtocolState.COMMAND, 5)
        log.debug('in command mode')

        self.driver_client.cmd_dvr('start_direct')
        self.assert_state_change(PARProtocolState.DIRECT_ACCESS, 5)
        log.debug('in direct access')

        time.sleep(3)

        self.driver_client.cmd_dvr('stop_direct')
        # time.sleep(5)
        self.assert_state_change(PARProtocolState.COMMAND, 5)
        log.debug('leaving direct access')

    def test_errors(self):
        """
        Verify response to erroneous commands and setting bad parameters.
        """
        self.assert_initialize_driver(PARProtocolState.COMMAND)

        #Assert an invalid command
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

        # Assert for a known command, invalid state.
        self.assert_driver_command_exception(PARProtocolEvent.STOP_AUTOSAMPLE,
                                             exception_class=InstrumentCommandException)

        # Assert set fails with a bad parameter (not ALL or a list).
        self.assert_set_exception('I am a bogus param.', exception_class=InstrumentParameterException)   # TODO: range checking?

        # #Assert set fails with bad parameter and bad value
        self.assert_set_exception('I am a bogus param.', value='bogus value',
                                  exception_class=InstrumentParameterException)

        # put driver in disconnected state.
        self.driver_client.cmd_dvr('disconnect')

        # Assert for a known command, invalid state.
        self.assert_driver_command_exception(PARProtocolEvent.STOP_AUTOSAMPLE, exception_class=InstrumentCommandException)

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

    def test_scheduled_status_command(self):
        """
        Verify the device status command can be triggered and run in command
        """
        self.assert_initialize_driver()
        self.assert_set(EngineeringParameter.ACQUIRE_STATUS_INTERVAL, "00:00:20")

        # Verify that the event got scheduled
        self.assert_async_particle_generation(DataParticleType.CONFIG, self.assert_driver_parameters, timeout=60)

        # Reset the interval
        self.assert_set(EngineeringParameter.ACQUIRE_STATUS_INTERVAL, "00:00:10")

        # Verify that the event got scheduled
        self.assert_async_particle_generation(DataParticleType.CONFIG, self.assert_driver_parameters, timeout=30)

        # This should unschedule the acquire status event
        self.assert_set(EngineeringParameter.ACQUIRE_STATUS_INTERVAL, "00:00:00")

        # Now verify that no more status particles get generated, provide generous timeout
        failed = False

        try:
            self.assert_async_particle_generation(DataParticleType.CONFIG, self.assert_driver_parameters, timeout=100)

            # We should never get here, failed should remain False
            failed = True
        except AssertionError:
            pass

        self.assertFalse(failed)

        self.assert_current_state(PARProtocolState.COMMAND)

@attr('UNIT', group='mi')
class SatlanticParDecoratorTest(MiTestCase):
    
    def setUp(self):
        self.checksum_decorator = SatlanticChecksumDecorator()

    @unittest.skip("Needs to be revisited.  Is this used?")
    def test_checksum(self):
        self.assertEquals(("SATPAR0229,10.01,2206748544,234", "SATPAR0229,10.01,2206748544,234"),
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

    # @unittest.skip('temp disable, working')
    def test_direct_access_telnet_mode(self):
        """
        This test manually tests that the Instrument Driver properly supports direct access to the
        physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)
        log.debug('finished set up')

        # self.tcp_client.send_data(EOLN)
        # time.sleep(0.4)
        # result = self.tcp_client.expect("Invalid command")
        # self.assertTrue(result)

        log.debug("DA Server Started.")

        self.tcp_client.send_data("t    e    s    t")
        time.sleep(0.4)
        self.tcp_client.send_data(EOLN)
        time.sleep(0.4)
        self.tcp_client.expect("Invalid command")

        self.tcp_client.send_data("s    e    t         m    a    x    r    a    t    e         1")
        time.sleep(0.4)
        self.tcp_client.send_data(EOLN)
        time.sleep(0.4)

        self.tcp_client.send_data("s    a    v    e")
        time.sleep(0.4)
        self.tcp_client.send_data(EOLN)
        time.sleep(0.4)
        self.tcp_client.expect("$")

        self.assert_direct_access_stop_telnet()

        self.assert_state_change(ResourceAgentState.COMMAND, PARProtocolState.COMMAND, 10)

        # verify the setting got restored.
        self.assert_get_parameter(Parameter.MAXRATE, 4)

        self.assert_get_parameter(Parameter.FIRMWARE, "1.0.0")
        self.assert_get_parameter(Parameter.SERIAL, "4278190306")
        self.assert_get_parameter(Parameter.INSTRUMENT, "SATPAR")

        # Test direct access inactivity timeout
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=90)
        self.assert_state_change(ResourceAgentState.COMMAND, PARProtocolState.COMMAND, 60)

        # Test session timeout without activity
        self.assert_direct_access_start_telnet(inactivity_timeout=120, session_timeout=30)
        self.assert_state_change(ResourceAgentState.COMMAND, PARProtocolState.COMMAND, 60)

        # Test direct access session timeout with activity
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=60)
        # Send some activity every 30 seconds to keep DA alive.
        for i in range(1, 2, 3):
            self.tcp_client.send_data(EOLN)
            log.debug("Sending a little keep alive communication, sleeping for 15 seconds")
            time.sleep(15)

        self.assert_state_change(ResourceAgentState.COMMAND, PARProtocolState.COMMAND, 45)

    # @unittest.skip('temp disable, working')
    def test_get_set_parameters(self):
        """
        Verify that parameters can be get/set properly
        """
        self.assert_enter_command_mode()

        #read/write params
        self.assert_set_parameter(Parameter.MAXRATE, 2)

        #read-only params
        self.assert_get_parameter(Parameter.FIRMWARE, "1.0.0")
        self.assert_get_parameter(Parameter.SERIAL, "4278190306")
        self.assert_get_parameter(Parameter.INSTRUMENT, "SATPAR")

    # @unittest.skip('temp disable, working')
    def test_poll(self):
        """
        Verify data particles for a single sample that are specific to Parad
        """
        self.assert_enter_command_mode()
        self.assert_particle_polled(DriverEvent.ACQUIRE_SAMPLE, self.assert_particle_sample, DataParticleType.PARSED,
                                    timeout=10, sample_count=1)

    # @unittest.skip('temp disable, working')
    def test_autosample(self):
        """
        Verify data particles for auto-sampling that are specific to Parad
        """
        self.assert_enter_command_mode()
        self.assert_start_autosample()

        self.assert_particle_async(DataParticleType.PARSED, self.assert_particle_sample)

        self.assert_stop_autosample()

    # @unittest.skip('temp disable, working')
    def test_acquire_status(self):

        """
        Verify the driver can command an acquire status from the instrument
        """
        self.assert_enter_command_mode()

        # Begin streaming.
        self.assert_particle_polled(PARCapability.ACQUIRE_STATUS, self.assert_driver_parameters, DataParticleType.CONFIG)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

    # @unittest.skip('temp disable, working')
    def test_direct_access_telnet_mode_autosample(self):
        """
        Verify Direct Access can start autosampling for the instrument, and if stopping DA, the
        driver will resort to Autosample State. Also, testing disconnect
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        log.debug("DA Server Started. Put system into autosample")
        time.sleep(2)

        self.tcp_client.send_data("e    x    i    t")
        time.sleep(0.4)
        self.tcp_client.send_data(EOLN)

        time.sleep(2)
        log.debug("DA autosample started")

        #Assert if stopping DA while autosampling, discover will put driver into Autosample state
        self.assert_direct_access_stop_telnet()
        time.sleep(2)
        self.assert_state_change(ResourceAgentState.STREAMING, PARProtocolState.AUTOSAMPLE, timeout=20)

    # @unittest.skip('temp disable, working')
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
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [PARProtocolEvent.GET,
                                                               PARProtocolEvent.SET,
                                                               PARProtocolEvent.ACQUIRE_SAMPLE,
                                                               PARProtocolEvent.ACQUIRE_STATUS,
                                                               PARProtocolEvent.SCHEDULED_ACQUIRE_STATUS,
                                                               PARProtocolEvent.START_AUTOSAMPLE,
                                                               PARProtocolEvent.START_DIRECT]
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = None
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = self._driver_parameters.keys()

        self.assert_enter_command_mode()
        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################
        capabilities = {}
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [PARProtocolEvent.STOP_AUTOSAMPLE,
                                                              PARProtocolEvent.SCHEDULED_ACQUIRE_STATUS,
                                                              PARProtocolEvent.RESET]
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