#!/usr/bin/env python
"""
@package mi.instrument.satlantic.ocr_507_icsw.ooicore.test.test_driver
@file marine-integrations/mi/instrument/satlantic/ocr_507_icsw/ooicore/driver.py
@author Godfrey Duke
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

import time
import unittest
from nose.plugins.attrib import attr
from mock import Mock

from pyon.agent.agent import ResourceAgentState
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import DataParticleValue
from mi.core.instrument.chunker import StringChunker
from mi.idk.unit_test import DriverTestMixin, InstrumentDriverTestCase, DriverStartupConfigKey
from mi.idk.unit_test import ParameterTestConfigKey
from mi.core.exceptions import InstrumentCommandException
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import AgentCapabilityType
from mi.instrument.satlantic.ocr_507_icsw.ooicore.driver import DataParticleType, \
    SatlanticOCR507ConfigurationParticleKey, EOLN
from mi.instrument.satlantic.ocr_507_icsw.ooicore.driver import SatlanticOCR507InstrumentProtocol
from mi.instrument.satlantic.ocr_507_icsw.ooicore.driver import SatlanticProtocolState
from mi.instrument.satlantic.ocr_507_icsw.ooicore.driver import SatlanticProtocolEvent
from mi.instrument.satlantic.ocr_507_icsw.ooicore.driver import SatlanticCapability
from mi.instrument.satlantic.ocr_507_icsw.ooicore.driver import Parameter
from mi.instrument.satlantic.ocr_507_icsw.ooicore.driver import Command
from mi.instrument.satlantic.ocr_507_icsw.ooicore.driver import Prompt
from mi.instrument.satlantic.ocr_507_icsw.ooicore.driver import SatlanticOCR507DataParticle
from mi.instrument.satlantic.ocr_507_icsw.ooicore.driver import SatlanticOCR507DataParticleKey
from mi.instrument.satlantic.ocr_507_icsw.ooicore.driver import SatlanticOCR507InstrumentDriver
from mi.core.log import get_logger


__author__ = 'Godfrey Duke'
__license__ = 'Apache 2.0'

log = get_logger()

# Initialize the test parameters
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.satlantic.ocr_507_icsw.ooicore.driver',
    driver_class="SatlanticOCR507InstrumentDriver",

    instrument_agent_resource_id='123xyz',
    instrument_agent_preload_id='IA2',
    instrument_agent_name='Agent007',
    instrument_agent_packet_config=DataParticleType(),
    driver_startup_config={
        DriverStartupConfigKey.PARAMETERS: {
            Parameter.MAX_RATE: '0',
            Parameter.INIT_SM: True,
            Parameter.INIT_AT: True,
            Parameter.NET_MODE: False
        }
    }
)


VALID_SAMPLE_INVALID_CHECKSUM = 'SATDI702331310692.31\xff{\x80\x01\xae\x80\x80\x1a\xfc\x80\x80&\x98\x00\x80\x05"\xc0\x80#z@\x809\xc9@\x80\x03\xff\xc0\x01\x1a\x00\xaf\x00\xa1\x14\xc3\r\n'
VALID_SAMPLE_VALID_CHECKSUM = 'SATDI702330316551.83\xff{\x80\x00\x12\x00\x80\t\xed\xc0\x80\x01\xd6\xc0\x80\x01\xea\x80\x80\x0f\x84\x00\x80\x12\xc8\x00\x80\x00\x90\x00\x01\x1b\x00\xaf\x00\xa2\xc4\x9c\r\n'


# Make tests verbose and provide stdout
# bin/nosetests -s -v ion/services/mi/drivers/test/test_satlantic_par.py
# All unit tests: add "-a UNIT" to end, integration add "-a INT"
# Test device is at 10.180.80.173, port 2001

VALID_CONFIG = "Satlantic OCR-507 Multispectral Radiometer\r\n" + \
               "Copyright (C) 2002, Satlantic Inc. All rights reserved.\r\n" + \
               "Firmware version: 3.0A - SatNet Type B\r\n" + \
               "Instrument: SATDI7\r\n" + \
               "S/N: 0233\r\n" + \
               "\r\n" + \
               "[Auto]$ " + \
               "Telemetry Baud Rate: 57600 bps" + \
               "Maximum Frame Rate: 1 Hz" + \
               "Initialize Silent Mode: off" + \
               "Initialize Power Down: off" + \
               "Initialize Automatic Telemetry: on" + \
               "Network Mode: off" + \
               "Network Address: 100" + \
               "Network Baud Rate: 38400 bps" + \
               "\r\n" + \
               "[Auto"


class SatlanticMixin(DriverTestMixin):
    """
    Mixin class used for storing data particle constance and common data assertion methods.
    """
    # Create some short names for the parameter test config
    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    STATES = ParameterTestConfigKey.STATES

    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.MAX_RATE: {TYPE: str, READONLY: False, DA: True, STARTUP: True, VALUE: '0'},
        Parameter.INIT_SM: {TYPE: bool, READONLY: True, DA: True, STARTUP: True, VALUE: True},
        Parameter.INIT_AT: {TYPE: bool, READONLY: True, DA: True, STARTUP: True, VALUE: True},
        Parameter.NET_MODE: {TYPE: bool, READONLY: True, DA: True, STARTUP: True, VALUE: False},
    }

    _sample_parameters = {
        SatlanticOCR507DataParticleKey.INSTRUMENT_ID: {TYPE: unicode, VALUE: 'SATDI7', REQUIRED: True},
        SatlanticOCR507DataParticleKey.SERIAL_NUMBER: {TYPE: unicode, VALUE: '0233', REQUIRED: True},
        SatlanticOCR507DataParticleKey.TIMER: {TYPE: float, VALUE: 1310692.31, REQUIRED: True},
        SatlanticOCR507DataParticleKey.SAMPLE_DELAY: {TYPE: int, VALUE: -133, REQUIRED: True},
        SatlanticOCR507DataParticleKey.SAMPLES: {TYPE: list, VALUE: [2147593856,
                                                                     2149252224,
                                                                     2150012928,
                                                                     2147820224,
                                                                     2149808704,
                                                                     2151270720,
                                                                     2147745728], REQUIRED: True},
        SatlanticOCR507DataParticleKey.REGULATED_INPUT_VOLTAGE: {TYPE: int, VALUE: 282, REQUIRED: True},
        SatlanticOCR507DataParticleKey.ANALOG_RAIL_VOLTAGE: {TYPE: int, VALUE: 175, REQUIRED: True},
        SatlanticOCR507DataParticleKey.INTERNAL_TEMP: {TYPE: int, VALUE: 161, REQUIRED: True},
        SatlanticOCR507DataParticleKey.FRAME_COUNTER: {TYPE: int, VALUE: 20, REQUIRED: True},
        SatlanticOCR507DataParticleKey.CHECKSUM: {TYPE: int, VALUE: 195, REQUIRED: True}
    }

    _config_parameters = {
        SatlanticOCR507ConfigurationParticleKey.FIRMWARE_VERSION: {TYPE: unicode, VALUE: '3.0A - SatNet Type B',
                                                                   REQUIRED: True},
        SatlanticOCR507ConfigurationParticleKey.INSTRUMENT_ID: {TYPE: unicode, VALUE: 'SATDI7', REQUIRED: True},
        SatlanticOCR507ConfigurationParticleKey.SERIAL_NUMBER: {TYPE: unicode, VALUE: '0233', REQUIRED: True},
        SatlanticOCR507ConfigurationParticleKey.TELEMETRY_BAUD_RATE: {TYPE: int, VALUE: 57600, REQUIRED: True},
        SatlanticOCR507ConfigurationParticleKey.MAX_FRAME_RATE: {TYPE: unicode, VALUE: '1', REQUIRED: True},
        SatlanticOCR507ConfigurationParticleKey.INIT_SILENT_MODE: {TYPE: bool, VALUE: False, REQUIRED: True},
        SatlanticOCR507ConfigurationParticleKey.INIT_POWER_DOWN: {TYPE: bool, VALUE: False, REQUIRED: True},
        SatlanticOCR507ConfigurationParticleKey.INIT_AUTO_TELEMETRY: {TYPE: bool, VALUE: True, REQUIRED: True},
        SatlanticOCR507ConfigurationParticleKey.NETWORK_MODE: {TYPE: bool, VALUE: False, REQUIRED: True},
        SatlanticOCR507ConfigurationParticleKey.NETWORK_ADDRESS: {TYPE: int, VALUE: 100, REQUIRED: True},
        SatlanticOCR507ConfigurationParticleKey.NETWORK_BAUD_RATE: {TYPE: int, VALUE: 38400, REQUIRED: True}
    }

    _driver_capabilities = {
        # capabilities defined in the IOS
        SatlanticCapability.START_AUTOSAMPLE: {STATES: [SatlanticProtocolState.COMMAND]},
        SatlanticCapability.STOP_AUTOSAMPLE: {STATES: [SatlanticProtocolState.AUTOSAMPLE]},
        SatlanticCapability.ACQUIRE_STATUS: {STATES: [SatlanticProtocolState.COMMAND]},
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
        log.debug('data_particle: %r', data_particle)
        self.assert_data_particle_keys(SatlanticOCR507DataParticleKey, self._sample_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.PARSED)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)

    def assert_particle_config(self, data_particle, verify_values=False):
        """
        Verify sample particle
        @param data_particle:  SBE16DataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        """
        log.debug('data_particle: %r', data_particle)
        self.assert_data_particle_keys(SatlanticOCR507ConfigurationParticleKey, self._config_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.CONFIG)
        self.assert_data_particle_parameters(data_particle, self._config_parameters, verify_values)


@attr('UNIT', group='mi')
class SatlanticProtocolUnitTest(InstrumentDriverUnitTestCase, SatlanticMixin):
    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(Command())
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(SatlanticProtocolState())
        self.assert_enum_has_no_duplicates(SatlanticProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(SatlanticCapability())
        self.assert_enum_complete(SatlanticCapability(), SatlanticProtocolEvent())

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        driver = SatlanticOCR507InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)

    def test_chunker(self):
        """
        Tests the chunker
        """
        # This will want to be created in the driver eventually...
        chunker = StringChunker(SatlanticOCR507InstrumentProtocol.sieve_function)

        for sample in [ VALID_SAMPLE_INVALID_CHECKSUM, VALID_SAMPLE_VALID_CHECKSUM, VALID_CONFIG ]:
            self.assert_chunker_sample(chunker, sample)
            self.assert_chunker_fragmented_sample(chunker, sample)
            self.assert_chunker_combined_sample(chunker, sample)
            self.assert_chunker_sample_with_noise(chunker, sample)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = SatlanticOCR507InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, VALID_SAMPLE_INVALID_CHECKSUM, self.assert_particle_sample, True)
        self.assert_particle_published(driver, VALID_CONFIG, self.assert_particle_config, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
        protocol = SatlanticOCR507InstrumentProtocol(mock_callback)
        driver_capabilities = SatlanticCapability().list()
        test_capabilities = SatlanticCapability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            SatlanticProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
            SatlanticProtocolState.COMMAND: ['DRIVER_EVENT_GET',
                                             'DRIVER_EVENT_SET',
                                             'DRIVER_EVENT_START_AUTOSAMPLE',
                                             'DRIVER_EVENT_ACQUIRE_STATUS',
                                             'DRIVER_EVENT_START_DIRECT'],
            SatlanticProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_STOP_AUTOSAMPLE'],
            SatlanticProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT',
                                                   'EXECUTE_DIRECT']
        }

        driver = SatlanticOCR507InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)

    def test_checksum(self):
        """
        Verify the checksum validation occurs as expected.
        """
        valid_checksum_particle = SatlanticOCR507DataParticle(VALID_SAMPLE_VALID_CHECKSUM)
        valid_checksum_particle.generate_dict()
        if valid_checksum_particle.contents[DataParticleKey.QUALITY_FLAG] is DataParticleValue.CHECKSUM_FAILED:
            self.fail('SatlanticOCR507DataParticle validity flag set incorrectly - should be set to true')

        invalid_checksum_particle = SatlanticOCR507DataParticle(VALID_SAMPLE_INVALID_CHECKSUM)
        invalid_checksum_particle.generate_dict()
        if invalid_checksum_particle.contents[DataParticleKey.QUALITY_FLAG] is not DataParticleValue.CHECKSUM_FAILED:
            self.fail('SatlanticOCR507DataParticle validity flag set incorrectly - should be set to false')


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, SatlanticMixin):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_commands(self):
        """
        Run instrument commands from command mode.
        """
        self.assert_initialize_driver(SatlanticProtocolState.COMMAND)

        ####
        # Test invalid state transitions from command
        ####
        self.assert_driver_command_exception(SatlanticProtocolEvent.STOP_AUTOSAMPLE,
                                             exception_class=InstrumentCommandException)

        ####
        # Test valid commands from command
        ####
        self.assert_driver_command(SatlanticProtocolEvent.START_AUTOSAMPLE, state=SatlanticProtocolState.AUTOSAMPLE)

        ####
        # Test invalid state transitions from autosample
        ####
        self.assert_driver_command_exception(SatlanticProtocolEvent.START_AUTOSAMPLE,
                                             exception_class=InstrumentCommandException)

        ####
        # Test valid commands from autosample
        ####
        self.assert_driver_command(SatlanticProtocolEvent.STOP_AUTOSAMPLE, state=SatlanticProtocolState.COMMAND)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

    def test_autosample_and_status_particle_gen(self):
        """
        Verify that we can enter streaming and that all particles are produced
        properly.

        Because we have to test for different data particles we can't use
        the common assert_sample_autosample method

        1. initialize the instrument to COMMAND state
        2. command the instrument to AUTOSAMPLE
        3. verify the particle coming in
        4. command the instrument to STOP AUTOSAMPLE state
        5. verify the particle coming in
        """
        self.assert_initialize_driver()
        self.assert_driver_command(SatlanticProtocolEvent.START_AUTOSAMPLE, state=SatlanticProtocolState.AUTOSAMPLE)
        self.assert_async_particle_generation(DataParticleType.PARSED, self.assert_particle_sample, timeout=30)
        self.assert_driver_command(SatlanticProtocolEvent.STOP_AUTOSAMPLE, state=SatlanticProtocolState.COMMAND)
        self.assert_driver_command(SatlanticProtocolEvent.ACQUIRE_STATUS, state=SatlanticProtocolState.COMMAND)
        self.assert_async_particle_generation(DataParticleType.CONFIG, self.assert_particle_config, timeout=30)

    def test_startup_parameter_defaults(self):
        self.assert_initialize_driver()
        self.assert_get(Parameter.MAX_RATE, self._driver_parameters[Parameter.MAX_RATE][self.VALUE])
        self.assert_get(Parameter.INIT_SM, self._driver_parameters[Parameter.INIT_SM][self.VALUE])
        self.assert_get(Parameter.INIT_AT, self._driver_parameters[Parameter.INIT_AT][self.VALUE])
        self.assert_get(Parameter.NET_MODE, self._driver_parameters[Parameter.NET_MODE][self.VALUE])

    def test_parameters(self):
        """
        Verify that we can set the parameters

        1. Cannot set read only parameters
        2. Can set read/write parameters
        3. Can set read/write parameters w/direct access only
        4. Cannot set bad parameter values
        5. Cannot get/set a bad parameter
        """
        self.assert_initialize_driver(SatlanticProtocolState.COMMAND)

        #test read/write parameter
        self.assert_set(Parameter.MAX_RATE, '2.0')

        #test setting immutable parameters when startup
        self.assert_set(Parameter.INIT_SM, False, startup=True, no_get=True)
        self.assert_get(Parameter.INIT_SM, False)

        self.assert_set(Parameter.INIT_AT, False, startup=True, no_get=True)
        self.assert_get(Parameter.INIT_AT, False)

        # Set the netmode to True (This should never be True: make sure not to leave it like this...)
        self.assert_set(Parameter.NET_MODE, True, startup=True, no_get=True)
        self.assert_get(Parameter.NET_MODE, True)
        # Set the netmode back to False (Phew! That was close!)
        self.assert_set(Parameter.NET_MODE, False, startup=True, no_get=True)
        self.assert_get(Parameter.NET_MODE, False)

        #test read only parameter (includes immutable, when not startup)- should not be set, value should not change
        self.assert_set_exception(Parameter.INIT_SM, True)
        self.assert_set_exception(Parameter.INIT_AT, True)
        self.assert_set_exception(Parameter.NET_MODE, True)
        self.assert_set_exception(Parameter.NET_MODE, False)

        # test set bad param values
        self.assert_set_exception(Parameter.NET_MODE, 'Do a barrel roll!')
        self.assert_set_exception(Parameter.MAX_RATE, '40')
        # test get/set bad param
        self.assert_set_exception('bad_param', False)
        with self.assertRaises(Exception):
            self.assert_get('bad_param', False)

    def test_direct_access(self):
        """
        Verify we can enter the direct access state
        """
        self.assert_initialize_driver(SatlanticProtocolState.COMMAND)
        self.assert_state_change(SatlanticProtocolState.COMMAND, 5)
        self.driver_client.cmd_dvr('execute_resource', SatlanticProtocolEvent.START_DIRECT)
        self.assert_state_change(SatlanticProtocolState.DIRECT_ACCESS, 5)

        self.driver_client.cmd_dvr('execute_resource', SatlanticProtocolEvent.STOP_DIRECT)
        self.assert_state_change(SatlanticProtocolState.COMMAND, 5)
        log.debug('leaving direct access')


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class SatlanticProtocolQualificationTest(InstrumentDriverQualificationTestCase, SatlanticMixin):
    """Qualification Test Container"""

    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.

    def test_direct_access_telnet_mode(self):
        """
        @brief This test verifies that the Instrument Driver
               properly supports direct access to the physical
               instrument. (telnet mode)
        """
        ###
        # First test direct access and exit with a go command
        # call.  Also add a parameter change to verify DA
        # parameters are restored on DA exit.
        ###
        self.assert_enter_command_mode()
        self.assert_get_parameter(Parameter.MAX_RATE, self._driver_parameters[Parameter.MAX_RATE][self.VALUE])
        self.assert_get_parameter(Parameter.INIT_AT, self._driver_parameters[Parameter.INIT_AT][self.VALUE])
        self.assert_get_parameter(Parameter.INIT_SM, self._driver_parameters[Parameter.INIT_SM][self.VALUE])
        self.assert_get_parameter(Parameter.NET_MODE, self._driver_parameters[Parameter.NET_MODE][self.VALUE])

        # go into direct access, and modify the DA parameters
        self.assert_direct_access_start_telnet()
        self.tcp_client.send_data("set maxrate 1")
        self.assertTrue(self.tcp_client.expect(Prompt.COMMAND))
        self.tcp_client.send_data("show maxrate")
        self.assertTrue(self.tcp_client.expect('Maximum Frame Rate: 1 Hz'))
        self.assertTrue(self.tcp_client.expect(Prompt.COMMAND))

        self.tcp_client.send_data("set initat off")
        self.assertTrue(self.tcp_client.expect(Prompt.COMMAND))
        self.tcp_client.send_data("show initat")
        self.assertTrue(self.tcp_client.expect('Initialize Automatic Telemetry: off'))
        self.assertTrue(self.tcp_client.expect(Prompt.COMMAND))

        self.tcp_client.send_data("set initsm off")
        self.assertTrue(self.tcp_client.expect(Prompt.COMMAND))
        self.tcp_client.send_data("show initsm")
        self.assertTrue(self.tcp_client.expect('Initialize Silent Mode: off'))
        self.assertTrue(self.tcp_client.expect(Prompt.COMMAND))

        self.tcp_client.send_data("set netmode on")
        self.assertTrue(self.tcp_client.expect(Prompt.COMMAND))
        self.tcp_client.send_data("show netmode")
        self.assertTrue(self.tcp_client.expect('Network Mode: on'))
        self.assertTrue(self.tcp_client.expect(Prompt.COMMAND))

        #need to sleep as the instrument needs time to apply the new param value
        time.sleep(5)

        # Verify the param value got changed on the instrument
        self.tcp_client.send_data("show maxrate")
        time.sleep(0.4)

        self.assertTrue(self.tcp_client.expect("Maximum Frame Rate: 1 Hz"))
        self.assertTrue(self.tcp_client.expect(Prompt.COMMAND))
        self.assert_direct_access_stop_telnet()

        # verify the DA parameters revert to their pre-DA values
        self.assert_enter_command_mode()
        self.assert_get_parameter(Parameter.MAX_RATE, self._driver_parameters[Parameter.MAX_RATE][self.VALUE])
        self.assert_get_parameter(Parameter.INIT_AT, self._driver_parameters[Parameter.INIT_AT][self.VALUE])
        self.assert_get_parameter(Parameter.INIT_SM, self._driver_parameters[Parameter.INIT_SM][self.VALUE])
        self.assert_get_parameter(Parameter.NET_MODE, self._driver_parameters[Parameter.NET_MODE][self.VALUE])

    def test_direct_access_telnet_timeout(self):
        """
        Verify that direct access times out as expected and the agent transitions back to command mode.
        """
        self.assert_enter_command_mode()

        # go into direct access
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=90)
        self.assertTrue(self.tcp_client)

        self.assert_state_change(ResourceAgentState.COMMAND, SatlanticProtocolState.COMMAND, 180)

    def test_direct_access_telnet_mode_autosample(self):
        """
        Force the instrument into streaming when in DA.  Then we need to verify the transition back
        to the driver works as expected.
        """
        self.assert_enter_command_mode()

        # go into direct access
        self.assert_direct_access_start_telnet()

        self.tcp_client.send_data('exit!')

        #verify we're sampling
        self.assertTrue(self.tcp_client.expect('SATDI7', sleep_time=2))

        #Assert if stopping DA while autosampling, discover will put driver into Autosample state
        self.assert_direct_access_stop_telnet()
        self.assert_state_change(ResourceAgentState.STREAMING, SatlanticProtocolState.AUTOSAMPLE, timeout=10)

        #now stop autosampling
        self.assert_stop_autosample()

    def test_get_set_parameters(self):
        """
        Verify that parameters can be get/set properly
        """
        self.assert_enter_command_mode()

        #read/write params
        self.assert_set_parameter(Parameter.MAX_RATE, 2)

        #read-only params
        self.assert_get_parameter(Parameter.INIT_AT, True)
        self.assert_get_parameter(Parameter.INIT_SM, True)
        self.assert_get_parameter(Parameter.NET_MODE, False)

    def test_autosample(self):
        """
        Verify data particles for auto-sampling that are specific to SPKIR
        """
        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.MAX_RATE, 1)
        self.assert_start_autosample()

        self.assert_particle_async(DataParticleType.PARSED, self.assert_particle_sample, particle_count=10, timeout=12)

        self.assert_stop_autosample()

    def test_acquire_status(self):
        """
        Verify the driver can command an acquire status from the instrument
        """
        self.assert_enter_command_mode()

        self.assert_particle_polled(SatlanticCapability.ACQUIRE_STATUS, self.assert_particle_config,
                                    DataParticleType.CONFIG)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

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
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [SatlanticProtocolEvent.START_AUTOSAMPLE,
                                                              SatlanticProtocolEvent.ACQUIRE_STATUS]
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = None
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = self._driver_parameters.keys()

        self.assert_enter_command_mode()
        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################
        capabilities = {}
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [SatlanticProtocolEvent.STOP_AUTOSAMPLE]
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = self._driver_parameters.keys()

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        ###################
        #  DA Mode
        ###################
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []

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