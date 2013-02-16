"""
@package mi.instrument.seabird.sbe54tps.test.test_driver
@file mi/instrument/seabird/sbe54tps/test/test_driver.py
@author Roger Unwin
@brief Test cases for sbe54 driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v mi/instrument/seabird/sbe54tps/ooicore
       $ bin/nosetests -s -v mi/instrument/seabird/sbe54tps/ooicore -a UNIT
       $ bin/nosetests -s -v mi/instrument/seabird/sbe54tps/ooicore -a INT
       $ bin/nosetests -s -v mi/instrument/seabird/sbe54tps/ooicore -a QUAL
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock
import re
import time
import ntplib

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey

from interface.objects import AgentCommand
from mi.idk.util import convert_enum_to_dict

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_fsm import InstrumentFSM

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.seabird.sbe54tps.driver import SBE54PlusInstrumentDriver
from mi.instrument.seabird.sbe54tps.driver import ScheduledJob
from mi.instrument.seabird.sbe54tps.driver import ProtocolState
from mi.instrument.seabird.sbe54tps.driver import Parameter
from mi.instrument.seabird.sbe54tps.driver import ProtocolEvent
from mi.instrument.seabird.sbe54tps.driver import Capability
from mi.instrument.seabird.sbe54tps.driver import Prompt
from mi.instrument.seabird.sbe54tps.driver import Protocol
from mi.instrument.seabird.sbe54tps.driver import InstrumentCmds
from mi.instrument.seabird.sbe54tps.driver import NEWLINE
from mi.instrument.seabird.sbe54tps.driver import SBE54tpsStatusDataParticle, SBE54tpsStatusDataParticleKey
from mi.instrument.seabird.sbe54tps.driver import SBE54tpsEventCounterDataParticle, SBE54tpsEventCounterDataParticleKey
from mi.instrument.seabird.sbe54tps.driver import SBE54tpsSampleDataParticle, SBE54tpsSampleDataParticleKey
from mi.instrument.seabird.sbe54tps.driver import SBE54tpsHardwareDataParticle, SBE54tpsHardwareDataParticleKey
from mi.instrument.seabird.sbe54tps.driver import SBE54tpsConfigurationDataParticle, SBE54tpsConfigurationDataParticleKey
from mi.instrument.seabird.sbe54tps.driver import SBE54tpsSampleRefOscDataParticle, SBE54tpsSampleRefOscDataParticleKey
from mi.instrument.seabird.sbe54tps.driver import DataParticleType

from mi.instrument.seabird.test.test_driver import SeaBirdUnitTest
from mi.instrument.seabird.test.test_driver import SeaBirdIntegrationTest
from mi.instrument.seabird.test.test_driver import SeaBirdQualificationTest

from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue

# SAMPLE DATA FOR TESTING
from mi.instrument.seabird.sbe54tps.test.sample_data import *

from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

from mi.core.exceptions import SampleException, InstrumentParameterException, InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException, InstrumentCommandException
from pyon.core.exception import Conflict
from mi.core.instrument.instrument_driver import DriverParameter, DriverConnectionState, DriverAsyncEvent
from mi.core.instrument.chunker import StringChunker

# Globals
raw_stream_received = False
parsed_stream_received = False

class SeaBird54tpsMixin(DriverTestMixin):
    '''
    Mixin class used for storing data particle constance and common data assertion methods.
    '''
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
        Parameter.SAMPLE_PERIOD : {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 15, VALUE: 15},
        Parameter.TIME : {TYPE: str, READONLY: False, DA: False, STARTUP: False},
        Parameter.BATTERY_TYPE : {TYPE: int, READONLY: True, DA: True, STARTUP: True, DEFAULT: 1, VALUE: 1},
        Parameter.ENABLE_ALERTS : {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: True, VALUE: 1},
    }

    _prest_real_time_parameters = {
        SBE54tpsSampleDataParticleKey.SAMPLE_NUMBER: {TYPE: int, VALUE: 5947, REQUIRED: True },
        SBE54tpsSampleDataParticleKey.SAMPLE_TYPE: {TYPE: unicode, VALUE: 'Pressure', REQUIRED: True },
        SBE54tpsSampleDataParticleKey.INST_TIME: {TYPE: unicode, VALUE: '2012-11-07T12:21:25', REQUIRED: True },
        SBE54tpsSampleDataParticleKey.PRESSURE: {TYPE: float, VALUE: 13.9669, REQUIRED: True },
        SBE54tpsSampleDataParticleKey.PRESSURE_TEMP: {TYPE: float, VALUE: 18.9047, REQUIRED: True },
    }

    _prest_reference_oscillator_parameters = {
        SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT: {TYPE: int, VALUE: 15000, REQUIRED: True },
        SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_MAX: {TYPE: int, VALUE: 0, REQUIRED: True },
        SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_ICD: {TYPE: int, VALUE: 15000, REQUIRED: True },
        SBE54tpsSampleRefOscDataParticleKey.SAMPLE_NUMBER: {TYPE: int, VALUE: 1244, REQUIRED: False },
        SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TYPE: {TYPE: unicode, VALUE: 'RefOsc', REQUIRED: False },
        SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TIMESTAMP: {TYPE: float, VALUE: 3558413454.0, REQUIRED: False },
        SBE54tpsSampleRefOscDataParticleKey.REF_OSC_FREQ: {TYPE: float, VALUE: 5999995.955, REQUIRED: False },
        SBE54tpsSampleRefOscDataParticleKey.REF_ERROR_PPM: {TYPE: float, VALUE: 0.090, REQUIRED: False },
        SBE54tpsSampleRefOscDataParticleKey.PCB_TEMP_RAW: {TYPE: int, VALUE: 18413, REQUIRED: False },
    }

    _prest_configuration_data_parameters = {
        SBE54tpsConfigurationDataParticleKey.DEVICE_TYPE: {TYPE: unicode, VALUE: 'SBE54' , REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.SERIAL_NUMBER: {TYPE: int, VALUE: 5400012, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.ACQ_OSC_CAL_DATE: {TYPE: unicode, VALUE: '2012-02-20', REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.FRA0: {TYPE: float, VALUE: 5.999926E+06, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.FRA1: {TYPE: float, VALUE: 5.792290E-03, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.FRA2: {TYPE: float, VALUE: -1.195664E-07, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.FRA3: {TYPE: float, VALUE: 7.018589E-13, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PRESSURE_SERIAL_NUM: {TYPE: int, VALUE: 121451, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PRESSURE_CAL_DATE: {TYPE: unicode, VALUE: '2011-06-01', REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PU0: {TYPE: float, VALUE: 5.820407E+00, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PY1: {TYPE: float, VALUE: -3.845374E+03, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PY2: {TYPE: float, VALUE: -1.078882E+04, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PY3: {TYPE: float, VALUE: 0.000000E+00, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PC1: {TYPE: float, VALUE: -2.700543E+04, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PC2: {TYPE: float, VALUE: -1.738438E+03, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PC3: {TYPE: float, VALUE: 7.629962E+04, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PD1: {TYPE: float, VALUE: 3.739600E-02, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PD2: {TYPE: float, VALUE: 0.000000E+00, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PT1: {TYPE: float, VALUE: 3.027306E+01, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PT2: {TYPE: float, VALUE: 2.231025E-01, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PT3: {TYPE: float, VALUE: 5.398972E+01, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PT4: {TYPE: float, VALUE: 1.455506E+02, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PRESSURE_OFFSET: {TYPE: float, VALUE: 0.000000E+00, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.PRESSURE_RANGE: {TYPE: float, VALUE: 6.000000E+03, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.BATTERY_TYPE: {TYPE: int, VALUE: 0, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.BAUD_RATE: {TYPE: int, VALUE: 9600, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.ENABLE_ALERTS: {TYPE: bool, VALUE: False, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.UPLOAD_TYPE: {TYPE: int, VALUE: 0, REQUIRED: True },
        SBE54tpsConfigurationDataParticleKey.SAMPLE_PERIOD: {TYPE: int, VALUE: 15, REQUIRED: True }
    }

    _prest_device_status_parameters = {
        SBE54tpsStatusDataParticleKey.DEVICE_TYPE: {TYPE: unicode, VALUE: 'SBE54', REQUIRED: True },
        SBE54tpsStatusDataParticleKey.SERIAL_NUMBER: {TYPE: int, VALUE: 5400012, REQUIRED: True },
        SBE54tpsStatusDataParticleKey.TIME: {TYPE: unicode, VALUE: '2012-11-06T10:55:44', REQUIRED: True },
        SBE54tpsStatusDataParticleKey.EVENT_COUNT: {TYPE: int, VALUE: 573 },
        SBE54tpsStatusDataParticleKey.MAIN_SUPPLY_VOLTAGE: {TYPE: float, VALUE:  23.3, REQUIRED: True },
        SBE54tpsStatusDataParticleKey.NUMBER_OF_SAMPLES: {TYPE: int, VALUE: 22618, REQUIRED: True },
        SBE54tpsStatusDataParticleKey.BYTES_USED: {TYPE: int, VALUE: 341504, REQUIRED: True },
        SBE54tpsStatusDataParticleKey.BYTES_FREE: {TYPE: int, VALUE: 133876224, REQUIRED: True },
    }

    _prest_event_counter_parameters = {
        SBE54tpsEventCounterDataParticleKey.NUMBER_EVENTS: {TYPE: int, VALUE: 573 },
        SBE54tpsEventCounterDataParticleKey.MAX_STACK: {TYPE: int, VALUE: 354 },
        SBE54tpsEventCounterDataParticleKey.DEVICE_TYPE: {TYPE: unicode, VALUE: 'SBE54' },
        SBE54tpsEventCounterDataParticleKey.SERIAL_NUMBER: {TYPE: int, VALUE: 5400012 },
        SBE54tpsEventCounterDataParticleKey.POWER_ON_RESET: {TYPE: int, VALUE: 25 },
        SBE54tpsEventCounterDataParticleKey.POWER_FAIL_RESET: {TYPE: int, VALUE: 25 },
        SBE54tpsEventCounterDataParticleKey.SERIAL_BYTE_ERROR: {TYPE: int, VALUE: 9 },
        SBE54tpsEventCounterDataParticleKey.COMMAND_BUFFER_OVERFLOW: {TYPE: int, VALUE: 1 },
        SBE54tpsEventCounterDataParticleKey.SERIAL_RECEIVE_OVERFLOW: {TYPE: int, VALUE: 255 },
        SBE54tpsEventCounterDataParticleKey.LOW_BATTERY: {TYPE: int, VALUE: 255 },
        SBE54tpsEventCounterDataParticleKey.SIGNAL_ERROR: {TYPE: int, VALUE: 1 },
        SBE54tpsEventCounterDataParticleKey.ERROR_10: {TYPE: int, VALUE: 1 },
        SBE54tpsEventCounterDataParticleKey.ERROR_12: {TYPE: int, VALUE: 1 },
    }

    _prest_hardware_data_parameters = {
        SBE54tpsHardwareDataParticleKey.DEVICE_TYPE: {TYPE: unicode, VALUE: 'SBE54', REQUIRED: True },
        SBE54tpsHardwareDataParticleKey.SERIAL_NUMBER: {TYPE: int, VALUE: 5400012, REQUIRED: True },
        SBE54tpsHardwareDataParticleKey.MANUFACTURER: {TYPE: unicode, VALUE: 'Sea-Bird Electronics, Inc', REQUIRED: True },
        SBE54tpsHardwareDataParticleKey.FIRMWARE_VERSION: {TYPE: unicode, VALUE: 'SBE54 V1.3-6MHZ', REQUIRED: True },
        SBE54tpsHardwareDataParticleKey.FIRMWARE_DATE: {TYPE: unicode, VALUE: 'Mar 22 2007', REQUIRED: True },
        SBE54tpsHardwareDataParticleKey.HARDWARE_VERSION: {TYPE: unicode, VALUE: '41478A.1T', REQUIRED: True },
        SBE54tpsHardwareDataParticleKey.PCB_SERIAL_NUMBER: {TYPE: unicode, VALUE: 'NOT SET', REQUIRED: True },
        SBE54tpsHardwareDataParticleKey.PCB_TYPE: {TYPE: unicode, VALUE: '1', REQUIRED: True },
        SBE54tpsHardwareDataParticleKey.MANUFACTUR_DATE: {TYPE: unicode, VALUE: 'Jun 27 2007', REQUIRED: True },
    }

    ###
    #   Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values = False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    def assert_particle_real_time(self, data_particle, verify_values = False):
        '''
        Verify prest_real_tim particle
        @param data_particle:  SBE54tpsSampleDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SBE54tpsSampleDataParticleKey, self._prest_real_time_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.PREST_REAL_TIME)
        self.assert_data_particle_parameters(data_particle, self._prest_real_time_parameters, verify_values)

    def assert_particle_reference_oscillator(self, data_particle, verify_values = False):
        '''
        Verify prest_reference_oscillator particle
        @param data_particle:  SBE54tpsSampleRefOscDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SBE54tpsSampleRefOscDataParticleKey, self._prest_reference_oscillator_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.PREST_REFERENCE_OSCILLATOR)
        self.assert_data_particle_parameters(data_particle, self._prest_reference_oscillator_parameters, verify_values)

    def assert_particle_configuration_data(self, data_particle, verify_values = False):
        '''
        Verify prest_configuration_data particle
        @param data_particle:  SBE54tpsSampleDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SBE54tpsConfigurationDataParticleKey, self._prest_configuration_data_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.PREST_CONFIGURATION_DATA)
        self.assert_data_particle_parameters(data_particle, self._prest_configuration_data_parameters, verify_values)

    def assert_particle_device_status(self, data_particle, verify_values = False):
        '''
        Verify prest_device_status particle
        @param data_particle:  SBE54tpsStatusDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SBE54tpsStatusDataParticleKey, self._prest_device_status_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.PREST_DEVICE_STATUS)
        self.assert_data_particle_parameters(data_particle, self._prest_device_status_parameters, verify_values)

    def assert_particle_event_counter(self, data_particle, verify_values = False):
        '''
        Verify prest_event_coutner particle
        @param data_particle:  SBE54tpsEventCounterDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SBE54tpsEventCounterDataParticleKey, self._prest_event_counter_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.PREST_EVENT_COUNTER)
        self.assert_data_particle_parameters(data_particle, self._prest_event_counter_parameters, verify_values)

    def assert_particle_hardware_data(self, data_particle, verify_values = False):
        '''
        Verify prest_hardware_data particle
        @param data_particle:  SBE54tpsHardwareDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SBE54tpsHardwareDataParticleKey, self._prest_hardware_data_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.PREST_REAL_TIME)
        self.assert_data_particle_parameters(data_particle, self._prest_hardware_data_parameters, verify_values)


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class SeaBird54PlusUnitTest(SeaBirdUnitTest, SeaBird54tpsMixin):
    def setUp(self):
        SeaBirdUnitTest.setUp(self)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(ScheduledJob())
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(InstrumentCmds())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, SAMPLE_GETSD)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_GETSD)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_GETSD, 32)
        self.assert_chunker_combined_sample(chunker, SAMPLE_GETSD)

        self.assert_chunker_sample(chunker, SAMPLE_GETCD)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_GETCD)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_GETCD, 32)
        self.assert_chunker_combined_sample(chunker, SAMPLE_GETCD)

        self.assert_chunker_sample(chunker, SAMPLE_GETEC)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_GETEC)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_GETEC, 32)
        self.assert_chunker_combined_sample(chunker, SAMPLE_GETEC)

        self.assert_chunker_sample(chunker, SAMPLE_GETHD)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_GETHD)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_GETHD, 32)
        self.assert_chunker_combined_sample(chunker, SAMPLE_GETHD)

        self.assert_chunker_sample(chunker, SAMPLE_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_SAMPLE, 32)
        self.assert_chunker_combined_sample(chunker, SAMPLE_SAMPLE)

        self.assert_chunker_sample(chunker, SAMPLE_TEST_REF_OSC)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_TEST_REF_OSC)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_TEST_REF_OSC, 32)
        self.assert_chunker_combined_sample(chunker, SAMPLE_TEST_REF_OSC)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = SBE54PlusInstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, SAMPLE_GETSD, self.assert_particle_device_status, True)
        self.assert_particle_published(driver, SAMPLE_GETCD, self.assert_particle_configuration_data, True)
        self.assert_particle_published(driver, SAMPLE_GETEC, self.assert_particle_event_counter, True)
        self.assert_particle_published(driver, SAMPLE_GETHD, self.assert_particle_hardware_data, True)
        self.assert_particle_published(driver, SAMPLE_SAMPLE, self.assert_particle_real_time, True)
        self.assert_particle_published(driver, SAMPLE_TEST_REF_OSC, self.assert_particle_reference_oscillator, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = Protocol(Prompt, NEWLINE, my_event_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(driver_capabilities, protocol._filter_capabilities(test_capabilities))

    def test_driver_parameters(self):
        """
        Verify the set of parameters known by the driver
        """
        driver = SBE54PlusInstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        expected_parameters = sorted(self._driver_parameters.keys())
        reported_parameters = sorted(driver.get_resource(Parameter.ALL))

        log.debug("Reported Parameters: %s" % reported_parameters)
        log.debug("Expected Parameters: %s" % expected_parameters)

        self.assertEqual(reported_parameters, expected_parameters)

        # Verify the parameter definitions
        self.assert_driver_parameter_definition(driver, self._driver_parameters)

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
            ProtocolState.COMMAND: ['DRIVER_EVENT_ACQUIRE_STATUS',
                                    'DRIVER_EVENT_CLOCK_SYNC',
                                    'DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET',
                                    'DRIVER_EVENT_START_AUTOSAMPLE',
                                    'DRIVER_EVENT_START_DIRECT',
                                    'PROTOCOL_EVENT_INIT_LOGGING',
                                    'PROTOCOL_EVENT_RESET_EC',
                                    'PROTOCOL_EVENT_SAMPLE_REFERENCE_OSCILLATOR',
                                    'PROTOCOL_EVENT_GET_CONFIGURATION',
                                    'PROTOCOL_EVENT_GET_STATUS',
                                    'PROTOCOL_EVENT_GET_EVENT_COUNTER',
                                    'PROTOCOL_EVENT_GET_HARDWARE',
                                    'PROTOCOL_EVENT_TEST_EEPROM'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_GET',
                                       'DRIVER_EVENT_STOP_AUTOSAMPLE',
                                       'PROTOCOL_EVENT_GET_CONFIGURATION',
                                       'PROTOCOL_EVENT_GET_STATUS',
                                       'PROTOCOL_EVENT_GET_EVENT_COUNTER',
                                       'PROTOCOL_EVENT_GET_HARDWARE',
                                       'DRIVER_EVENT_ACQUIRE_STATUS'],
            ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT']
        }

        driver = SBE54PlusInstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class SeaBird54PlusIntegrationTest(SeaBirdIntegrationTest, SeaBird54tpsMixin):
    def setUp(self):
        SeaBirdIntegrationTest.setUp(self)

    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply, True)

    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()

        #   Instrument Parameteres

        # Sample Period.  integer 1 - 240
        self.assert_set(Parameter.SAMPLE_PERIOD, 1)
        self.assert_set(Parameter.SAMPLE_PERIOD, 240)
        self.assert_set_exception(Parameter.SAMPLE_PERIOD, 241)
        self.assert_set_exception(Parameter.SAMPLE_PERIOD, 0)
        self.assert_set_exception(Parameter.SAMPLE_PERIOD, -1)
        self.assert_set_exception(Parameter.SAMPLE_PERIOD, "1")

        #   Read only parameters
        self.assert_set_readonly(Parameter.BATTERY_TYPE, 1)
        self.assert_set_readonly(Parameter.ENABLE_ALERTS, True)

    def test_autosample(self):
        """
        Verify that we can enter streaming and that all particles are produced
        properly.

        Because we have to test for three different data particles we can't use
        the common assert_sample_autosample method
        """
        self.assert_initialize_driver()
        self.assert_set(Parameter.SAMPLE_PERIOD, 1)

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_async_particle_generation(DataParticleType.PREST_REAL_TIME, self.assert_particle_real_time, timeout=120)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

    def assert_particle_device_status(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusDeviceStatusDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.PREST_DEVICE_STATUS)
        self.assert_data_particle_parameters(data_particle, self._status_sample_parameters, verify_values)

    def test_polled_particle_generation(self):
        """
        Test that we can generate particles with commands
        """
        self.assert_initialize_driver()

        #self.assert_particle_generation(ProtocolEvent.SAMPLE_REFERENCE_OSCILLATOR, DataParticleType.PREST_REAL_TIME, self.assert_particle_tide_sample)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.PREST_DEVICE_STATUS, self.assert_particle_device_status)
        #self.assert_particle_generation(ProtocolEvent.ACQUIRE_CONFIGURATION, DataParticleType.DEVICE_CALIBRATION, self.assert_particle_device_calibration)

@attr('QUAL', group='mi')
class SeaBird54PlusQualificationTest(SeaBirdQualificationTest):
    def setUp(self):
        SeaBirdQualificationTest.setUp(self)

    ###
    #    Add instrument specific qualification tests
    ###

    def check_agent_state(self, desired_agent_state):
        """
        Transitions to the desired state, then verifies it has indeed made it to that state.
        @param desired_state: the state to transition to.
        """
        #@todo promote this to base class already....

        current_state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(current_state, desired_agent_state)

    def check_resource_state(self, desired_resource_state):
        """
        Transitions to the desired state, then verifies it has indeed made it to that state.
        @param desired_state: the state to transition to.
        """
        #@todo promote this to base class already....

        current_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(current_state, desired_resource_state)

    def assert_resource_command_and_resource_state(self, resource_command, desired_state):

        cmd = AgentCommand(command=resource_command)
        retval = self.instrument_agent_client.execute_resource(cmd)
        self.check_resource_state(desired_state)
        return retval

    def assert_agent_command_and_resource_state(self, resource_command, desired_state):

        cmd = AgentCommand(command=resource_command)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=60)
        self.check_resource_state(desired_state)
        return retval

    def assert_agent_command_and_agent_state(self, agent_command, desired_state):
        """
        Execute an agent command, and verify the desired state is achieved.
        @param agent_command: the agent command to execute
        @param desired_state: the state that should result
        """

        cmd = AgentCommand(command=agent_command)
        retval = self.instrument_agent_client.execute_agent(cmd)
        self.check_agent_state(desired_state)
        return retval

    def assert_capabilitys_present(self, agent_capabilities, required_capabilities):
        """
        Verify that both lists are the same, order independent.
        @param agent_capabilities
        @param required_capabilities
        """

        for agent_capability in agent_capabilities:
            self.assertTrue(agent_capability in required_capabilities)

        for desired_capability in required_capabilities:
            self.assertTrue(desired_capability in agent_capabilities)

    def get_current_capabilities(self):
        """
        return a list of currently available capabilities
        """
        result = self.instrument_agent_client.get_capabilities()

        agent_capabilities = []
        unknown = []
        driver_capabilities = []
        driver_vars = []

        for x in result:
            if x.cap_type == 1:
                agent_capabilities.append(x.name)
            elif x.cap_type == 2:
                unknown.append(x.name)
            elif x.cap_type == 3:
                driver_capabilities.append(x.name)
            elif x.cap_type == 4:
                driver_vars.append(x.name)
            else:
                log.debug("*UNKNOWN* " + str(repr(x)))

        return (agent_capabilities, unknown, driver_capabilities, driver_vars)

    # WORKS
    def check_state(self, desired_state):
        state = self.instrument_agent_client.get_resource_state()

        # 'DRIVER_STATE_AUTOSAMPLE' != 'DRIVER_STATE_COMMAND'
        if ProtocolState.AUTOSAMPLE == state:
            # OH SNAP! WE'RE IN AUTOSAMPLE AGAIN!
            # QUICK, FIX IT BEFORE ANYONE NOTICES!

            cmd = AgentCommand(command=ProtocolEvent.STOP_AUTOSAMPLE)

            retval = self.instrument_agent_client.execute_resource(cmd, timeout=60)

            state = self.instrument_agent_client.get_resource_state()
            #  ...AND MAKE LIKE THIS NEVER HAPPENED!
        self.assertEqual(state, desired_state)

    def assert_SBE54tpsStatusDataParticle(self, prospective_particle):
        """
        @param prospective_particle: a perfect particle of SBE54tpsStatusDataParticle or FAIL!!!!
        """
        sample_dict = prospective_particle

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
            DataParticleValue.PARSED)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        for x in sample_dict['values']:
            key = x['value_id']
            value = x['value']
            self.assertTrue(key in [
                SBE54tpsStatusDataParticleKey.DEVICE_TYPE,
                SBE54tpsStatusDataParticleKey.SERIAL_NUMBER,
                SBE54tpsStatusDataParticleKey.TIME,
                SBE54tpsStatusDataParticleKey.EVENT_COUNT,
                SBE54tpsStatusDataParticleKey.MAIN_SUPPLY_VOLTAGE,
                SBE54tpsStatusDataParticleKey.NUMBER_OF_SAMPLES,
                SBE54tpsStatusDataParticleKey.BYTES_USED,
                SBE54tpsStatusDataParticleKey.BYTES_FREE
            ])

            # CHECK THAT THE TYPES ARE CORRECT IN THE DICT.
            # str
            if key in [
                SBE54tpsStatusDataParticleKey.DEVICE_TYPE,
                SBE54tpsStatusDataParticleKey.TIME
            ]:
                self.assertTrue(isinstance(value, str))
            # int
            elif key in [
                SBE54tpsStatusDataParticleKey.SERIAL_NUMBER,
                SBE54tpsStatusDataParticleKey.EVENT_COUNT,
                SBE54tpsStatusDataParticleKey.NUMBER_OF_SAMPLES,
                SBE54tpsStatusDataParticleKey.BYTES_USED,
                SBE54tpsStatusDataParticleKey.BYTES_FREE
            ]:
                self.assertTrue(isinstance(value, int))
            #float
            elif key in [
                SBE54tpsStatusDataParticleKey.MAIN_SUPPLY_VOLTAGE
            ]:
                self.assertTrue(isinstance(value, float))
            else:
                # SHOULD NEVER GET HERE. IF WE DO FAIL, SO IT IS INVESTIGATED
                self.assertTrue(False)

    # WORKS
    def assert_SBE54tpsConfigurationDataParticle(self, prospective_particle):
        """
        @param prospective_particle: a perfect particle of SBE54tpsStatusDataParticle or FAIL!!!!
        """
        sample_dict = prospective_particle

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
            DataParticleValue.PARSED)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        for x in sample_dict['values']:
            key = x['value_id']
            value = x['value']
            self.assertTrue(key in [
                SBE54tpsConfigurationDataParticleKey.DEVICE_TYPE,
                SBE54tpsConfigurationDataParticleKey.PRESSURE_SERIAL_NUM,
                SBE54tpsConfigurationDataParticleKey.SERIAL_NUMBER,
                SBE54tpsConfigurationDataParticleKey.BATTERY_TYPE,
                SBE54tpsConfigurationDataParticleKey.ENABLE_ALERTS,
                SBE54tpsConfigurationDataParticleKey.UPLOAD_TYPE,
                SBE54tpsConfigurationDataParticleKey.SAMPLE_PERIOD,
                SBE54tpsConfigurationDataParticleKey.FRA0,
                SBE54tpsConfigurationDataParticleKey.FRA1,
                SBE54tpsConfigurationDataParticleKey.FRA2,
                SBE54tpsConfigurationDataParticleKey.FRA3,
                SBE54tpsConfigurationDataParticleKey.PU0,
                SBE54tpsConfigurationDataParticleKey.PY1,
                SBE54tpsConfigurationDataParticleKey.PY2,
                SBE54tpsConfigurationDataParticleKey.PY3,
                SBE54tpsConfigurationDataParticleKey.PC1,
                SBE54tpsConfigurationDataParticleKey.PC2,
                SBE54tpsConfigurationDataParticleKey.PC3,
                SBE54tpsConfigurationDataParticleKey.PD1,
                SBE54tpsConfigurationDataParticleKey.PD2,
                SBE54tpsConfigurationDataParticleKey.PT1,
                SBE54tpsConfigurationDataParticleKey.PT2,
                SBE54tpsConfigurationDataParticleKey.PT3,
                SBE54tpsConfigurationDataParticleKey.PT4,
                SBE54tpsConfigurationDataParticleKey.PRESSURE_OFFSET,
                SBE54tpsConfigurationDataParticleKey.PRESSURE_RANGE,
                SBE54tpsConfigurationDataParticleKey.ACQ_OSC_CAL_DATE,
                SBE54tpsConfigurationDataParticleKey.PRESSURE_CAL_DATE,
                SBE54tpsConfigurationDataParticleKey.BAUD_RATE
            ])

            # CHECK THAT THE TYPES ARE CORRECT IN THE DICT.
            # str
            if key in [
                SBE54tpsConfigurationDataParticleKey.DEVICE_TYPE,
                SBE54tpsConfigurationDataParticleKey.PRESSURE_SERIAL_NUM
                ]:
                self.assertTrue(isinstance(value, str))

            # int
            elif key in [
                SBE54tpsConfigurationDataParticleKey.SERIAL_NUMBER,
                SBE54tpsConfigurationDataParticleKey.BATTERY_TYPE,
                SBE54tpsConfigurationDataParticleKey.ENABLE_ALERTS,
                SBE54tpsConfigurationDataParticleKey.UPLOAD_TYPE,
                SBE54tpsConfigurationDataParticleKey.SAMPLE_PERIOD,
                SBE54tpsConfigurationDataParticleKey.BAUD_RATE
            ]:
                self.assertTrue(isinstance(value, int))

            #float
            elif key in [
                SBE54tpsConfigurationDataParticleKey.FRA0,
                SBE54tpsConfigurationDataParticleKey.FRA1,
                SBE54tpsConfigurationDataParticleKey.FRA2,
                SBE54tpsConfigurationDataParticleKey.FRA3,
                SBE54tpsConfigurationDataParticleKey.PU0,
                SBE54tpsConfigurationDataParticleKey.PY1,
                SBE54tpsConfigurationDataParticleKey.PY2,
                SBE54tpsConfigurationDataParticleKey.PY3,
                SBE54tpsConfigurationDataParticleKey.PC1,
                SBE54tpsConfigurationDataParticleKey.PC2,
                SBE54tpsConfigurationDataParticleKey.PC3,
                SBE54tpsConfigurationDataParticleKey.PD1,
                SBE54tpsConfigurationDataParticleKey.PD2,
                SBE54tpsConfigurationDataParticleKey.PT1,
                SBE54tpsConfigurationDataParticleKey.PT2,
                SBE54tpsConfigurationDataParticleKey.PT3,
                SBE54tpsConfigurationDataParticleKey.PT4,
                SBE54tpsConfigurationDataParticleKey.PRESSURE_OFFSET,
                SBE54tpsConfigurationDataParticleKey.PRESSURE_RANGE,
                # FLOAT DATE's
                SBE54tpsConfigurationDataParticleKey.ACQ_OSC_CAL_DATE,
                SBE54tpsConfigurationDataParticleKey.PRESSURE_CAL_DATE
            ]:
                self.assertTrue(isinstance(value, float))

            # date
            #elif key in [
            #    SBE54tpsConfigurationDataParticleKey.ACQ_OSC_CAL_DATE,
            #    SBE54tpsConfigurationDataParticleKey.PRESSURE_CAL_DATE
            #]:
            #    # @TODO add a date parser here
            #    self.assertTrue(isinstance(value, time.struct_time))
            else:
                # SHOULD NEVER GET HERE. IF WE DO FAIL, SO IT IS INVESTIGATED
                self.assertTrue(False)

    # WORKS
    def assert_SBE54tpsEventCounterDataParticle(self, prospective_particle):
        """
        @param prospective_particle: a perfect particle of SBE54tpsEventCounterDataParticle or FAIL!!!!
        """
        sample_dict = prospective_particle



        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
            DataParticleValue.PARSED)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        for x in sample_dict['values']:
            key = x['value_id']
            value = x['value']

            self.assertTrue(key in [
                SBE54tpsEventCounterDataParticleKey.NUMBER_EVENTS,
                SBE54tpsEventCounterDataParticleKey.MAX_STACK,
                SBE54tpsEventCounterDataParticleKey.DEVICE_TYPE,
                SBE54tpsEventCounterDataParticleKey.SERIAL_NUMBER,
                SBE54tpsEventCounterDataParticleKey.POWER_ON_RESET,
                SBE54tpsEventCounterDataParticleKey.POWER_FAIL_RESET,
                SBE54tpsEventCounterDataParticleKey.SERIAL_BYTE_ERROR,
                SBE54tpsEventCounterDataParticleKey.COMMAND_BUFFER_OVERFLOW,
                SBE54tpsEventCounterDataParticleKey.SERIAL_RECEIVE_OVERFLOW,
                SBE54tpsEventCounterDataParticleKey.LOW_BATTERY,
                SBE54tpsEventCounterDataParticleKey.SIGNAL_ERROR,
                SBE54tpsEventCounterDataParticleKey.ERROR_10,
                SBE54tpsEventCounterDataParticleKey.ERROR_12
            ])

            # CHECK THAT THE TYPES ARE CORRECT IN THE DICT.
            # int
            if key in [
                SBE54tpsEventCounterDataParticleKey.NUMBER_EVENTS,
                SBE54tpsEventCounterDataParticleKey.MAX_STACK,
                SBE54tpsEventCounterDataParticleKey.SERIAL_NUMBER,
                SBE54tpsEventCounterDataParticleKey.POWER_ON_RESET,
                SBE54tpsEventCounterDataParticleKey.POWER_FAIL_RESET,
                SBE54tpsEventCounterDataParticleKey.SERIAL_BYTE_ERROR,
                SBE54tpsEventCounterDataParticleKey.COMMAND_BUFFER_OVERFLOW,
                SBE54tpsEventCounterDataParticleKey.SERIAL_RECEIVE_OVERFLOW,
                SBE54tpsEventCounterDataParticleKey.LOW_BATTERY,
                SBE54tpsEventCounterDataParticleKey.SIGNAL_ERROR,
                SBE54tpsEventCounterDataParticleKey.ERROR_10,
                SBE54tpsEventCounterDataParticleKey.ERROR_12
            ]:
                log.debug("BAD ONE IS " + key)
                self.assertTrue(isinstance(value, int))

            # str
            elif key in [
                SBE54tpsEventCounterDataParticleKey.DEVICE_TYPE,
            ]:
                self.assertTrue(isinstance(value, str))

            else:
                # SHOULD NEVER GET HERE. IF WE DO FAIL, SO IT IS INVESTIGATED
                self.assertTrue(False)

    # WORKS
    def assert_SBE54tpsHardwareDataParticle(self, prospective_particle):
        """
        @param prospective_particle: a perfect particle of SBE54tpsHardwareDataParticle or FAIL!!!!
        """
        sample_dict = prospective_particle

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
            DataParticleValue.PARSED)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        for x in sample_dict['values']:
            key = x['value_id']
            value = x['value']

            self.assertTrue(key in [
                SBE54tpsHardwareDataParticleKey.DEVICE_TYPE,
                SBE54tpsHardwareDataParticleKey.MANUFACTURER,
                SBE54tpsHardwareDataParticleKey.FIRMWARE_VERSION,
                SBE54tpsHardwareDataParticleKey.HARDWARE_VERSION,
                SBE54tpsHardwareDataParticleKey.PCB_SERIAL_NUMBER,
                SBE54tpsHardwareDataParticleKey.PCB_TYPE,
                SBE54tpsHardwareDataParticleKey.SERIAL_NUMBER,
                SBE54tpsHardwareDataParticleKey.FIRMWARE_DATE,
                SBE54tpsHardwareDataParticleKey.MANUFACTUR_DATE
            ])

            # CHECK THAT THE TYPES ARE CORRECT IN THE DICT.
            # str
            if key in [
                SBE54tpsHardwareDataParticleKey.DEVICE_TYPE,
                SBE54tpsHardwareDataParticleKey.MANUFACTURER,
                SBE54tpsHardwareDataParticleKey.FIRMWARE_VERSION,
                SBE54tpsHardwareDataParticleKey.HARDWARE_VERSION,
                SBE54tpsHardwareDataParticleKey.PCB_SERIAL_NUMBER,
                SBE54tpsHardwareDataParticleKey.PCB_TYPE
                ]:
                self.assertTrue(isinstance(value, str))

            # int
            elif key in [
                SBE54tpsHardwareDataParticleKey.SERIAL_NUMBER
                ]:
                self.assertTrue(isinstance(value, int))

            # float
            elif key in [
                SBE54tpsHardwareDataParticleKey.FIRMWARE_DATE,
                SBE54tpsHardwareDataParticleKey.MANUFACTUR_DATE
            ]:
                # @TODO add a date parser here
                self.assertTrue(isinstance(value, float))
            else:
                # SHOULD NEVER GET HERE. IF WE DO FAIL, SO IT IS INVESTIGATED
                self.assertTrue(False)

    # WORKS
    def assert_SBE54tpsSampleDataParticle(self, prospective_particle):
        """
        @param prospective_particle: a perfect particle of SBE54tpsSampleDataParticle or FAIL!!!!
        """

        sample_dict = prospective_particle

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
            DataParticleValue.PARSED)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        for x in sample_dict['values']:
            key = x['value_id']
            value = x['value']
            self.assertTrue(key in [
                SBE54tpsSampleDataParticleKey.SAMPLE_TYPE,
                SBE54tpsSampleDataParticleKey.SAMPLE_NUMBER,
                SBE54tpsSampleDataParticleKey.PRESSURE,
                SBE54tpsSampleDataParticleKey.PRESSURE_TEMP,
                SBE54tpsSampleDataParticleKey.INST_TIME
            ])

            # CHECK THAT THE TYPES ARE CORRECT IN THE DICT.
            # str
            if key in [
                SBE54tpsSampleDataParticleKey.SAMPLE_TYPE,
                SBE54tpsSampleDataParticleKey.INST_TIME
                ]:
                self.assertTrue(isinstance(value, str))

            # int
            elif key in [
                SBE54tpsSampleDataParticleKey.SAMPLE_NUMBER
                ]:
                self.assertTrue(isinstance(value, int))

            #float
            elif key in [
                SBE54tpsSampleDataParticleKey.PRESSURE,
                SBE54tpsSampleDataParticleKey.PRESSURE_TEMP
                ]:
                self.assertTrue(isinstance(value, float))

            # date
            elif key in [
            ]:
                # @TODO add a date parser here
                self.assertTrue(isinstance(value, float))

            else:
                # SHOULD NEVER GET HERE. IF WE DO FAIL, SO IT IS INVESTIGATED
                self.assertTrue(False)

    # WORKS
    def assert_SBE54tpsSampleRefOscDataParticle(self, prospective_particle):
        """
        @param prospective_particle: a perfect particle of SBE54tpsSampleRefOscDataParticle or FAIL!!!!
        """

        sample_dict = prospective_particle

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
            DataParticleValue.PARSED)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        log.debug("SAMPLE_DICT[VALUES] = " + str(sample_dict['values']))

        for x in sample_dict['values']:
            key = x['value_id']
            value = x['value']
            log.debug("1KEY = " + key)
            log.debug("1VALUE = " + str(value))

            self.assertTrue(key in [
                SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT,
                SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_MAX,
                SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_ICD,
                SBE54tpsSampleRefOscDataParticleKey.SAMPLE_NUMBER,
                SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TYPE,
                SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TIMESTAMP,
                SBE54tpsSampleRefOscDataParticleKey.REF_OSC_FREQ,
                SBE54tpsSampleRefOscDataParticleKey.PCB_TEMP_RAW,
                SBE54tpsSampleRefOscDataParticleKey.REF_ERROR_PPM
            ])

            # CHECK THAT THE TYPES ARE CORRECT IN THE DICT.
            # str
            if key in [
                SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TYPE
            ]:
                self.assertTrue(isinstance(value, str))

            # int
            elif key in [
                SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT,
                SBE54tpsSampleRefOscDataParticleKey.SAMPLE_NUMBER,
                SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_MAX,
                SBE54tpsSampleRefOscDataParticleKey.SET_TIMEOUT_ICD,
                SBE54tpsSampleRefOscDataParticleKey.PCB_TEMP_RAW,
            ]:
                self.assertTrue(isinstance(value, int))

            #float
            elif key in [
                SBE54tpsSampleRefOscDataParticleKey.REF_OSC_FREQ,
                SBE54tpsSampleRefOscDataParticleKey.REF_ERROR_PPM,

                # timestamp
                SBE54tpsSampleRefOscDataParticleKey.SAMPLE_TIMESTAMP
            ]:
                log.debug("2KEY = " + key)
                log.debug("2VALUE = " + str(value))
                self.assertTrue(isinstance(value, float))

            else:
                # SHOULD NEVER GET HERE. IF WE DO FAIL, SO IT IS INVESTIGATED
                self.assertTrue(False)

    # WORKS
    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_enter_command_mode()



        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)
        self.tcp_client.send_data("\r\nsetSetSamplePeriod=97\r\n")
        self.tcp_client.expect("S>")

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()

        params = [
            Parameter.SAMPLE_PERIOD,
            ]
        new_params = self.instrument_agent_client.get_resource(params)
        log.debug("TESTING SAMPLE_PERIOD = " + repr(new_params))

        # assert that we altered the time.
        self.assertTrue(new_params[Parameter.SAMPLE_PERIOD] == 15)

    # WORKS
    def test_autosample(self):
        """
        @brief Test instrument driver execute interface to start and stop streaming
        mode.
        """
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)


        self.assert_enter_command_mode()

        # lets sample FAST!
        params = {
            Parameter.SAMPLE_PERIOD: 5
        }

        self.instrument_agent_client.set_resource(params, timeout=10)

        # Begin streaming.
        cmd = AgentCommand(command=ProtocolEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)

        self.data_subscribers.clear_sample_queue(DataParticleValue.PARSED)

        # wait for 3 samples, then test them!


        samples = self.data_subscribers.get_samples('parsed', 3, timeout=30)
        log.debug("GOT 3 SAMPLES I THINK!")



        self.assert_SBE54tpsSampleDataParticle(samples.pop())
        self.assert_SBE54tpsSampleDataParticle(samples.pop())
        self.assert_SBE54tpsSampleDataParticle(samples.pop())

        # Halt streaming.
        cmd = AgentCommand(command=ProtocolEvent.STOP_AUTOSAMPLE)

        retval = self.instrument_agent_client.execute_resource(cmd, timeout=60)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=10)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

    # WORKS
    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.

        This one needs to be re-written rather than copy/pasted to develop a better more reusable pattern.
        """

        # force it to command state before test so auto sample doesnt bork it up.
        self.assert_enter_command_mode()
        self.assert_reset()



        self.check_agent_state(ResourceAgentState.UNINITIALIZED)
        (agent_capabilities, unknown, driver_capabilities, driver_vars) = self.get_current_capabilities()
        self.assert_capabilitys_present(agent_capabilities, ['RESOURCE_AGENT_EVENT_INITIALIZE'])
        self.assert_capabilitys_present(driver_capabilities, [])

        log.debug("%%% STATE NOW ResourceAgentState.UNINITIALIZED")

        self.assert_agent_command_and_agent_state(ResourceAgentEvent.INITIALIZE, ResourceAgentState.INACTIVE)
        (agent_capabilities, unknown, driver_capabilities, driver_vars) = self.get_current_capabilities()
        self.assert_capabilitys_present(agent_capabilities, ['RESOURCE_AGENT_EVENT_GO_ACTIVE',
                                                             'RESOURCE_AGENT_EVENT_RESET'])
        self.assert_capabilitys_present(driver_capabilities, [])

        log.debug("%%% STATE NOW ResourceAgentState.INACTIVE")

        self.assert_agent_command_and_resource_state(ResourceAgentEvent.GO_ACTIVE, ProtocolState.COMMAND)
        (agent_capabilities, unknown, driver_capabilities, driver_vars) = self.get_current_capabilities()
        self.assert_capabilitys_present(agent_capabilities, ['RESOURCE_AGENT_EVENT_GO_INACTIVE',
                                                             'RESOURCE_AGENT_EVENT_RESET',
                                                             'RESOURCE_AGENT_EVENT_RUN'])
        self.assert_capabilitys_present(driver_capabilities, [])

        log.debug("%%% STATE NOW ResourceAgentState.IDLE")

        self.assert_agent_command_and_agent_state(ResourceAgentEvent.RUN, ResourceAgentState.COMMAND)

        log.debug("%%% STATE NOW ResourceAgentState.COMMAND")

        (agent_capabilities, unknown, driver_capabilities, driver_vars) = self.get_current_capabilities()
        log.debug("DRIVER CAPABILITIES = " +  str(driver_capabilities))
        self.assert_capabilitys_present(agent_capabilities, ['RESOURCE_AGENT_EVENT_CLEAR',
                                                             'RESOURCE_AGENT_EVENT_RESET',
                                                             'RESOURCE_AGENT_EVENT_GO_DIRECT_ACCESS',
                                                             'RESOURCE_AGENT_EVENT_GO_INACTIVE',
                                                             'RESOURCE_AGENT_EVENT_PAUSE'])
        self.assert_capabilitys_present(driver_capabilities, ['PROTOCOL_EVENT_RESET_EC', 'DRIVER_EVENT_ACQUIRE_STATUS',
                                                              'PROTOCOL_EVENT_TEST_EEPROM', 'PROTOCOL_EVENT_INIT_LOGGING',
                                                              'PROTOCOL_EVENT_SAMPLE_REFERENCE_OSCILLATOR', 'DRIVER_EVENT_START_AUTOSAMPLE',
                                                              'DRIVER_EVENT_CLOCK_SYNC'])


        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
                            kwargs={'session_type': DirectAccessTypes.telnet,
                                    #kwargs={'session_type':DirectAccessTypes.vsp,
                                    'session_timeout':600,
                                    'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)

        self.check_agent_state(ResourceAgentState.DIRECT_ACCESS)
        (agent_capabilities, unknown, driver_capabilities, driver_vars) = self.get_current_capabilities()
        self.assert_capabilitys_present(agent_capabilities, ['RESOURCE_AGENT_EVENT_GO_COMMAND'])
        self.assert_capabilitys_present(driver_capabilities, [])

    # WORKS
    def test_execute_clock_sync(self):
        """
        @brief Test Test EXECUTE_CLOCK_SYNC command.
        """
        self.assert_enter_command_mode()

        self.assert_resource_command_and_resource_state(ProtocolEvent.CLOCK_SYNC, ProtocolState.COMMAND)
        # clocl should now be synced

        # Now verify that at least the date matches
        params = [Parameter.TIME]
        check_new_params = self.instrument_agent_client.get_resource(params)
        lt = time.strftime("%d %b %Y  %H:%M:%S", time.gmtime(time.mktime(time.localtime())))

    # WORKS - BROKE - driver_startup_config not propigated via connect in assert_enter_command_mode
    def test_connect_disconnect(self):

        self.assert_enter_command_mode()

        # Change values of driver_startup_config variables
        params = {
            Parameter.SAMPLE_PERIOD: 5,
            Parameter.BATTERY_TYPE: 0,
            Parameter.ENABLE_ALERTS: 0
        }

        self.instrument_agent_client.set_resource(params, timeout=90)


        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)

        self.check_agent_state(ResourceAgentState.UNINITIALIZED)

        # Get back into command mode
        self.assert_enter_command_mode()


        '''
        self.??????.apply_startup_params()

        # Check that the defaults were reset
        params = [
            Parameter.SAMPLE_PERIOD,
            Parameter.BATTERY_TYPE,
            Parameter.ENABLE_ALERTS
        ]
        new_params = self.instrument_agent_client.get_resource(params)
        self.assertEqual(new_params[Parameter.SAMPLE_PERIOD], 15)
        self.assertEqual(new_params[Parameter.BATTERY_TYPE], 1)
        self.assertEqual(new_params[Parameter.ENABLE_ALERTS], 1)
        '''

    # WORKS
    def test_execute_set_time_parameter(self):
        """
        @brief Set the clock to a bogus date/time, then verify that after
        a discover opoeration it reverts to the system time.
        """

        self.assert_enter_command_mode()

        params = {
            Parameter.TIME : "2001-01-01T01:01:01",
            }

        self.instrument_agent_client.set_resource(params)

        params = [
            Parameter.TIME,
            ]
        check_new_params = self.instrument_agent_client.get_resource(params)
        log.debug("TESTING TIME = " + repr(check_new_params))

        # assert that we altered the time.
        self.assertTrue("2001-01-01T01:0" in check_new_params[Parameter.TIME])

        # now put it back to normal

        params = {
            Parameter.TIME : time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        }

        self.instrument_agent_client.set_resource(params)

        params = [
            Parameter.TIME,
            ]
        check_new_params = self.instrument_agent_client.get_resource(params)

        # Now verify that at least the date matches
        lt = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        self.assertTrue(lt[:12].upper() in check_new_params[Parameter.TIME].upper())

    # WORKS (dupe test_connect_disconnect)
    def test_execute_reset(self):
        """
        @brief Walk the driver into command mode and perform a reset
        verifying it goes back to UNINITIALIZED, then walk it back to
        COMMAND to test there are no glitches in RESET
        """
        self.assert_enter_command_mode()

        # Test RESET

        self.assert_reset()

        self.check_agent_state(ResourceAgentState.UNINITIALIZED)

        self.assert_enter_command_mode()

    # WORKS
    def test_execute_acquire_status(self):
        """
        @brief Test Test EXECUTE_CLOCK_SYNC command.
        """
        self.assert_enter_command_mode()

        result = self.assert_resource_command_and_resource_state(ProtocolEvent.ACQUIRE_STATUS, ProtocolState.COMMAND)

        log.debug("RESULT = " + result.result)
        # Lets assert some bits are present.
        # getcd
        self.assertTrue("<ConfigurationData DeviceType='SBE54'" in result.result)
        self.assertTrue("<CalibrationCoefficients>" in result.result)
        self.assertTrue("</CalibrationCoefficients>" in result.result)
        self.assertTrue("</ConfigurationData>" in result.result)


        # getsd
        self.assertTrue("<StatusData DeviceType='SBE54'" in result.result)
        self.assertTrue("MainSupplyVoltage" in result.result)

        #getec
        self.assertTrue("<EventList DeviceType='SBE54'" in result.result)
        # this one can be truncated, dont assert it too much


        # gethd
        self.assertTrue("<HardwareData DeviceType='SBE54'" in result.result)
        self.assertTrue("<Manufacturer>Sea-Bird Electronics, Inc</Manufacturer>" in result.result)
        self.assertTrue("</HardwareData>" in result.result)

    # WORKS
    def test_four_non_sample_particles(self):
        """
        @brief Test instrument driver execute interface to start and stop streaming
        mode.
        """
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        self.assert_enter_command_mode()


        self.data_subscribers.clear_sample_queue(DataParticleValue.PARSED)

        # AQUIRE STATUS. Should produce 4 particles.
        result = self.assert_resource_command_and_resource_state(ProtocolEvent.ACQUIRE_STATUS, ProtocolState.COMMAND)


        samples = self.data_subscribers.get_samples('parsed', 4, timeout=30)
        log.debug("GOT 4 SAMPLES I THINK!")

        sample = samples.pop()
        self.assert_SBE54tpsConfigurationDataParticle(sample)

        sample = samples.pop()
        self.assert_SBE54tpsStatusDataParticle(sample)

        sample = samples.pop()
        self.assert_SBE54tpsEventCounterDataParticle(sample)

        sample = samples.pop()
        self.assert_SBE54tpsHardwareDataParticle(sample)

    # WORKS
    def test_sample_ref_osc(self):
        """
        @brief Test initialize logging command.
        """
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        self.assert_enter_command_mode()

        # lets sample SLOW!
        params = {
            Parameter.SAMPLE_PERIOD: 120
        }

        self.instrument_agent_client.set_resource(params, timeout=10)

        # command takes 2+ minutes to warm up osc and take sample.
        # <!--Ref osc warmup next 120 seconds-->
        cmd = AgentCommand(command=ProtocolEvent.SAMPLE_REFERENCE_OSCILLATOR)

        self.data_subscribers.clear_sample_queue(DataParticleValue.PARSED)

        reply = self.instrument_agent_client.execute_resource(cmd, timeout=300)

        self.assertTrue("<SetTimeout>" in reply.result)
        self.assertTrue("<SetTimeoutMax>" in reply.result)
        self.assertTrue("<SetTimeoutICD>" in reply.result)
        self.assertTrue("<Sample Num='" in reply.result)
        self.assertTrue("<Time>" in reply.result)
        self.assertTrue("<RefOscFreq>" in reply.result)
        self.assertTrue("<PCBTempRaw>" in reply.result)
        self.assertTrue("<RefErrorPPM>" in reply.result)

        samples = self.data_subscribers.get_samples('parsed', 1, timeout=1)
        sample = samples.pop()
        self.assert_SBE54tpsSampleRefOscDataParticle(sample)

    # WORKS
    def test_test_eeprom(self):
        """
        @brief Test initialize logging command.
        """

        self.assert_enter_command_mode()

        # lets sample SLOW!
        params = {
            Parameter.SAMPLE_PERIOD: 120
        }

        self.instrument_agent_client.set_resource(params, timeout=10)

        cmd = AgentCommand(command=ProtocolEvent.TEST_EEPROM)

        reply = self.instrument_agent_client.execute_resource(cmd, timeout=300)

        self.assertTrue(reply.result)

    # WORKS
    def test_init_logging(self):
        """
        @brief Test initialize logging command.
        """

        self.assert_enter_command_mode()

        cmd = AgentCommand(command=ProtocolEvent.INIT_LOGGING)

        reply = self.instrument_agent_client.execute_resource(cmd, timeout=60)

        self.assertTrue(reply.result)

    def test_reset_ec(self):
        """
        @brief Test initialize logging command.
        """

        self.assert_enter_command_mode()

        cmd = AgentCommand(command=ProtocolEvent.RESET_EC)

        reply = self.instrument_agent_client.execute_resource(cmd, timeout=30)

        self.assertTrue(reply.result)

    # WORKS
    def assert_execute_agent_gets_exception(self, command):
        # Helper function for testing forcing exception
        cmd = AgentCommand(command=command)
        exception_happened = False
        try:
            reply = self.instrument_agent_client.execute_agent(cmd, timeout=30)
            log.debug(str(cmd) + " EXECUTED WIHTOUT EXCEPTION!!!!")
        except Conflict as ex:
            exception_happened = True
            log.debug("Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)

    # WORKS
    def assert_execute_resource_gets_exception(self, command):
        # Helper function for testing forcing exception
        cmd = AgentCommand(command=command)
        exception_happened = False
        try:
            reply = self.instrument_agent_client.execute_resource(cmd, timeout=30)
            log.debug(str(cmd) + " EXECUTED WIHTOUT EXCEPTION!!!!")
        except Conflict as ex:
            exception_happened = True
            log.debug("Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)

    # WORKS
    def test_execute_capability_from_bad_state(self):
        """
        @brief Run inappropriate capabilities at the entirely wrong time and make something exceptional happen
        """

        # force it to command state before test so auto sample doesnt bork it up.
        self.assert_enter_command_mode()
        self.assert_reset()



        self.check_agent_state(ResourceAgentState.UNINITIALIZED)
        #agent_capabilities, ['RESOURCE_AGENT_EVENT_INITIALIZE']
        #driver_capabilities, []

        #
        # Test some unreachable Agent capabilities
        #
        #self.assert_execute_agent_gets_exception(ResourceAgentEvent.INITIALIZE)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_ACTIVE)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_INACTIVE)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.RUN)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_DIRECT_ACCESS)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_COMMAND)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.PAUSE)

        #
        # Test some unreachable driver capabilities
        #
        self.assert_execute_resource_gets_exception(ProtocolEvent.RESET_EC)
        self.assert_execute_resource_gets_exception(ProtocolEvent.ACQUIRE_STATUS)
        self.assert_execute_resource_gets_exception(ProtocolEvent.TEST_EEPROM)
        self.assert_execute_resource_gets_exception(ProtocolEvent.INIT_LOGGING)
        self.assert_execute_resource_gets_exception(ProtocolEvent.SAMPLE_REFERENCE_OSCILLATOR)
        self.assert_execute_resource_gets_exception(ProtocolEvent.START_AUTOSAMPLE)
        self.assert_execute_resource_gets_exception(ProtocolEvent.CLOCK_SYNC)


        log.debug("%%% STATE NOW ResourceAgentState.UNINITIALIZED")

        self.assert_agent_command_and_agent_state(ResourceAgentEvent.INITIALIZE, ResourceAgentState.INACTIVE)
        #agent_capabilities, ['RESOURCE_AGENT_EVENT_GO_ACTIVE', 'RESOURCE_AGENT_EVENT_RESET']
        #driver_capabilities, []

        #
        # Test some unreachable Agent capabilities
        #
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.INITIALIZE)
        #self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_ACTIVE)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_INACTIVE)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.RUN)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_DIRECT_ACCESS)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_COMMAND)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.PAUSE)

        #
        # Test some unreachable driver capabilities
        #
        self.assert_execute_resource_gets_exception(ProtocolEvent.RESET_EC)
        self.assert_execute_resource_gets_exception(ProtocolEvent.ACQUIRE_STATUS)
        self.assert_execute_resource_gets_exception(ProtocolEvent.TEST_EEPROM)
        self.assert_execute_resource_gets_exception(ProtocolEvent.INIT_LOGGING)
        self.assert_execute_resource_gets_exception(ProtocolEvent.SAMPLE_REFERENCE_OSCILLATOR)
        self.assert_execute_resource_gets_exception(ProtocolEvent.START_AUTOSAMPLE)
        self.assert_execute_resource_gets_exception(ProtocolEvent.CLOCK_SYNC)


        log.debug("%%% STATE NOW ResourceAgentState.INACTIVE")

        self.assert_agent_command_and_resource_state(ResourceAgentEvent.GO_ACTIVE, ProtocolState.COMMAND)
        #agent_capabilities, ['RESOURCE_AGENT_EVENT_GO_INACTIVE', 'RESOURCE_AGENT_EVENT_RESET', 'RESOURCE_AGENT_EVENT_RUN']
        #driver_capabilities, []

        #
        # Test some unreachable Agent capabilities
        #
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.INITIALIZE)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_ACTIVE)
        #self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_INACTIVE)
        #self.assert_execute_agent_gets_exception(ResourceAgentEvent.RUN)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_DIRECT_ACCESS)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_COMMAND)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.PAUSE)
        #
        # Test some unreachable driver capabilities
        #
        self.assert_execute_resource_gets_exception(ProtocolEvent.RESET_EC)
        self.assert_execute_resource_gets_exception(ProtocolEvent.ACQUIRE_STATUS)
        self.assert_execute_resource_gets_exception(ProtocolEvent.TEST_EEPROM)
        self.assert_execute_resource_gets_exception(ProtocolEvent.INIT_LOGGING)
        self.assert_execute_resource_gets_exception(ProtocolEvent.SAMPLE_REFERENCE_OSCILLATOR)
        self.assert_execute_resource_gets_exception(ProtocolEvent.START_AUTOSAMPLE)
        self.assert_execute_resource_gets_exception(ProtocolEvent.CLOCK_SYNC)


        log.debug("%%% STATE NOW ResourceAgentState.IDLE")

        self.assert_agent_command_and_agent_state(ResourceAgentEvent.RUN, ResourceAgentState.COMMAND)

        log.debug("%%% STATE NOW ResourceAgentState.COMMAND")

        #agent_capabilities, ['RESOURCE_AGENT_EVENT_CLEAR', 'RESOURCE_AGENT_EVENT_RESET', 'RESOURCE_AGENT_EVENT_GO_DIRECT_ACCESS',
        #                     'RESOURCE_AGENT_EVENT_GO_INACTIVE', 'RESOURCE_AGENT_EVENT_PAUSE']
        #driver_capabilities, ['PROTOCOL_EVENT_RESET_EC', 'DRIVER_EVENT_ACQUIRE_STATUS', 'PROTOCOL_EVENT_TEST_EEPROM', 'PROTOCOL_EVENT_INIT_LOGGING', 'PROTOCOL_EVENT_SAMPLE_REFERENCE_OSCILLATOR', 'DRIVER_EVENT_START_AUTOSAMPLE', 'DRIVER_EVENT_CLOCK_SYNC']

        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
            kwargs={'session_type': DirectAccessTypes.telnet,
                    #kwargs={'session_type':DirectAccessTypes.vsp,
                    'session_timeout':600,
                    'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)

        self.check_agent_state(ResourceAgentState.DIRECT_ACCESS)
        #agent_capabilities, ['RESOURCE_AGENT_EVENT_GO_COMMAND']
        #driver_capabilities, []

        #
        # Test some unreachable Agent capabilities
        #
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.INITIALIZE)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_ACTIVE)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_INACTIVE)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.RUN)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_DIRECT_ACCESS)
        #self.assert_execute_agent_gets_exception(ResourceAgentEvent.GO_COMMAND)
        self.assert_execute_agent_gets_exception(ResourceAgentEvent.PAUSE)
        #
        # Test some unreachable driver capabilities
        #
        self.assert_execute_resource_gets_exception(ProtocolEvent.RESET_EC)
        self.assert_execute_resource_gets_exception(ProtocolEvent.ACQUIRE_STATUS)
        self.assert_execute_resource_gets_exception(ProtocolEvent.TEST_EEPROM)
        self.assert_execute_resource_gets_exception(ProtocolEvent.INIT_LOGGING)
        self.assert_execute_resource_gets_exception(ProtocolEvent.SAMPLE_REFERENCE_OSCILLATOR)
        self.assert_execute_resource_gets_exception(ProtocolEvent.START_AUTOSAMPLE)
        self.assert_execute_resource_gets_exception(ProtocolEvent.CLOCK_SYNC)



    def test_event_subscriber(self):

        self.addCleanup(self.event_subscribers.stop)

        self.event_subscribers.events_received = []
        count = 0
        self.assert_enter_command_mode()
        for ev in self.event_subscribers.events_received:
            count = count + 1
            log.debug(str(count) + " test_event_subscriber EVENTS = " + repr(ev))

        self.assertTrue(False) # enable debug PITA!!!!

        """
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 1 test_event_subscriber EVENTS = <interface.objects.ResourceAgentErrorEvent object at 0x1083750d0>
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 2 test_event_subscriber EVENTS = <interface.objects.ResourceAgentStateEvent object at 0x1082c5310>
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 3 test_event_subscriber EVENTS = <interface.objects.ResourceAgentCommandEvent object at 0x1082c5ad0>
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 4 test_event_subscriber EVENTS = <interface.objects.ResourceAgentResourceStateEvent object at 0x1082c9b90>
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 5 test_event_subscriber EVENTS = <interface.objects.ResourceAgentResourceStateEvent object at 0x1082cd910>
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 6 test_event_subscriber EVENTS = <interface.objects.ResourceAgentResourceStateEvent object at 0x1082c9ed0>
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 7 test_event_subscriber EVENTS = <interface.objects.ResourceAgentResourceStateEvent object at 0x108360410>
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 8 test_event_subscriber EVENTS = <interface.objects.ResourceAgentStateEvent object at 0x10835f9d0>
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 9 test_event_subscriber EVENTS = <interface.objects.ResourceAgentCommandEvent object at 0x108353bd0>
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 10 test_event_subscriber EVENTS = <interface.objects.ResourceAgentResourceConfigEvent object at 0x105923c50>
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 11 test_event_subscriber EVENTS = <interface.objects.ResourceAgentResourceStateEvent object at 0x105928590>
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 12 test_event_subscriber EVENTS = <interface.objects.ResourceAgentStateEvent object at 0x108314110>
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: 13 test_event_subscriber EVENTS = <interface.objects.ResourceAgentCommandEvent object at 0x105928b90>
        """