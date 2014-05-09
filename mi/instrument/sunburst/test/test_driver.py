"""
@package mi.instrument.sunburst.test.test_driver
@file marine-integrations/mi/instrument/sunburst/driver.py
@author Stuart Pearce & Chris Wingard
@brief Common test case code for SAMI instrument drivers

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Kevin Stiemke'
__license__ = 'Apache 2.0'

import unittest
import time
import datetime
import copy

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger
log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import GO_ACTIVE_TIMEOUT
from mi.idk.unit_test import DriverProtocolState
from mi.idk.unit_test import DriverEvent
from mi.idk.unit_test import ResourceAgentState
from mi.idk.unit_test import AgentCapabilityType
from pyon.agent.agent import ResourceAgentEvent
from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

# Might need these for later Integration tests and Qualification tests
#from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
#from ion.agents.instrument.instrument_agent import InstrumentAgentState
#from mi.core.instrument.instrument_driver import DriverAsyncEvent
#from mi.core.instrument.instrument_driver import DriverConnectionState
#from mi.core.instrument.instrument_driver import DriverProtocolState

from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import DataParticleValue

from mi.instrument.sunburst.driver import Prompt
from mi.instrument.sunburst.driver import NEWLINE
from mi.instrument.sunburst.driver import SamiControlRecordDataParticleKey
from mi.instrument.sunburst.driver import SamiDataParticleType
from mi.instrument.sunburst.driver import SamiRegularStatusDataParticleKey
from mi.instrument.sunburst.driver import SamiBatteryVoltageDataParticleKey
from mi.instrument.sunburst.driver import SamiThermistorVoltageDataParticleKey
from mi.instrument.sunburst.driver import SamiProtocolState
from mi.instrument.sunburst.driver import SamiDataParticleType
from mi.instrument.sunburst.driver import SamiProtocolEvent
from mi.instrument.sunburst.driver import SamiProtocol
from mi.instrument.sunburst.driver import SAMI_UNIX_OFFSET

TIME_THRESHOLD = 2

###
#   Driver parameters for the tests
###


#################################### RULES ####################################
#                                                                             #
# Common capabilities in the base class                                       #
#                                                                             #
# Instrument specific stuff in the derived class                              #
#                                                                             #
# Generator spits out either stubs or comments describing test this here,     #
# test that there.                                                            #
#                                                                             #
# Qualification tests are driven through the instrument_agent                 #
#                                                                             #
###############################################################################

###
#   Driver constant definitions
###

# Create some short names for the parameter test config
TYPE = ParameterTestConfigKey.TYPE
READONLY = ParameterTestConfigKey.READONLY
STARTUP = ParameterTestConfigKey.STARTUP
DA = ParameterTestConfigKey.DIRECT_ACCESS
VALUE = ParameterTestConfigKey.VALUE
REQUIRED = ParameterTestConfigKey.REQUIRED
DEFAULT = ParameterTestConfigKey.DEFAULT
STATES = ParameterTestConfigKey.STATES

###############################################################################
#                           DRIVER TEST MIXIN        		                  #
#     Defines a set of constants and assert methods used for data particle    #
#     verification 														      #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.									  #
###############################################################################


class SamiMixin(DriverTestMixin):
    '''
    Mixin class used for storing SAMI instrument data particle constants and common data
    assertion methods.

    Should be subclassed in the specific test driver
    '''

    ###
    #  Instrument output (driver input) Definitions
    ###

    # Control records
    VALID_CONTROL_RECORD = '*F81285CDDD74DD0041000003000000000224FC' + NEWLINE

    # Regular Status Message (response to S0 command)
    VALID_STATUS_MESSAGE = ':CDDD74E10041000003000000000236F8' + NEWLINE

    # Error records (valid error codes are between 0x00 and 0x11)
    VALID_ERROR_CODE = '?0B' + NEWLINE

    ###
    #  Parameter and Type Definitions
    ###

    _regular_status_parameters = {
        # SAMI Regular Status Messages (S0)
        SamiRegularStatusDataParticleKey.ELAPSED_TIME_CONFIG:     {TYPE: int, VALUE: 0xCDDD74E1, REQUIRED: True},
        SamiRegularStatusDataParticleKey.CLOCK_ACTIVE:            {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORDING_ACTIVE:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORD_END_ON_TIME:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORD_MEMORY_FULL:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORD_END_ON_ERROR:     {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.DATA_DOWNLOAD_OK:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.FLASH_MEMORY_OPEN:       {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiRegularStatusDataParticleKey.BATTERY_LOW_PRESTART:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.BATTERY_LOW_MEASUREMENT: {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.BATTERY_LOW_BANK:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.BATTERY_LOW_EXTERNAL:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE1_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE2_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE3_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.FLASH_ERASED:            {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.POWER_ON_INVALID:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.NUM_DATA_RECORDS:        {TYPE: int, VALUE: 0x000003, REQUIRED: True},
        SamiRegularStatusDataParticleKey.NUM_ERROR_RECORDS:       {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        SamiRegularStatusDataParticleKey.NUM_BYTES_STORED:        {TYPE: int, VALUE: 0x000236, REQUIRED: True},
        SamiRegularStatusDataParticleKey.UNIQUE_ID:                {TYPE: int, VALUE: 0xF8, REQUIRED: True}
    }

    _control_record_parameters = {
        SamiControlRecordDataParticleKey.UNIQUE_ID:               {TYPE: int, VALUE: 0xF8, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_LENGTH:           {TYPE: int, VALUE: 0x12, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_TYPE:             {TYPE: int, VALUE: 0x85,  REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_TIME:             {TYPE: int, VALUE: 0xCDDD74DD, REQUIRED: True},
        SamiControlRecordDataParticleKey.CLOCK_ACTIVE:            {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORDING_ACTIVE:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_END_ON_TIME:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_MEMORY_FULL:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_END_ON_ERROR:     {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.DATA_DOWNLOAD_OK:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.FLASH_MEMORY_OPEN:       {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_PRESTART:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_MEASUREMENT: {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_BANK:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_EXTERNAL:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.EXTERNAL_DEVICE1_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.EXTERNAL_DEVICE2_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.EXTERNAL_DEVICE3_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.FLASH_ERASED:            {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.POWER_ON_INVALID:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.NUM_DATA_RECORDS:        {TYPE: int, VALUE: 0x000003, REQUIRED: True},
        SamiControlRecordDataParticleKey.NUM_ERROR_RECORDS:       {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        SamiControlRecordDataParticleKey.NUM_BYTES_STORED:        {TYPE: int, VALUE: 0x000224, REQUIRED: True},
        SamiControlRecordDataParticleKey.CHECKSUM:                {TYPE: int, VALUE: 0xFC, REQUIRED: True}
    }

    _battery_voltage_parameters = {
        SamiBatteryVoltageDataParticleKey.BATTERY_VOLTAGE:        {TYPE: int, VALUE: 0x0CD8, REQUIRED: True}
    }

    _thermistor_voltage_parameters = {
        SamiThermistorVoltageDataParticleKey.THERMISTOR_VOLTAGE:  {TYPE: int, VALUE: 0x067B, REQUIRED: True}
    }

    def assert_particle_battery_voltage(self, data_particle, verify_values=False):
        '''
        Verify battery voltage particle
        @param data_particle: SamiBatteryVoltageDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SamiBatteryVoltageDataParticleKey,
                                       self._battery_voltage_parameters)
        self.assert_data_particle_header(data_particle,
                                         SamiDataParticleType.BATTERY_VOLTAGE)
        self.assert_data_particle_parameters(data_particle,
                                             self._battery_voltage_parameters,
                                             verify_values)

    def assert_particle_thermistor_voltage(self, data_particle, verify_values=False):
        '''
        Verify thermistor voltage particle
        @param data_particle: SamiThermistorVoltageDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SamiThermistorVoltageDataParticleKey,
                                       self._thermistor_voltage_parameters)
        self.assert_data_particle_header(data_particle,
                                         SamiDataParticleType.THERMISTOR_VOLTAGE)
        self.assert_data_particle_parameters(data_particle,
                                             self._thermistor_voltage_parameters,
                                             verify_values)

    def assert_driver_parameters(self, current_parameters, verify_values=False):
        """
        Verify that all driver parameters are correct and potentially verify
        values.
        @param current_parameters: driver parameters read from the driver
        instance
        @param verify_values: should we verify values against definition?
        """

        self.assert_parameters(current_parameters, self._driver_parameters,
                               verify_values)

    def assert_particle_regular_status(self, data_particle, verify_values=False):
        '''
        Verify regular_status particle
        @param data_particle: SamiRegularStatusDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''

        self.assert_data_particle_keys(SamiRegularStatusDataParticleKey,
                                       self._regular_status_parameters)
        self.assert_data_particle_header(data_particle,
                                         SamiDataParticleType.REGULAR_STATUS)
        self.assert_data_particle_parameters(data_particle,
                                             self._regular_status_parameters,
                                             verify_values)

    def assert_particle_control_record(self, data_particle, verify_values=False):
        '''
        Verify control_record particle
        @param data_particle: SamiControlRecordDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''

        self.assert_data_particle_keys(SamiControlRecordDataParticleKey,
                                       self._control_record_parameters)
        self.assert_data_particle_header(data_particle,
                                         SamiDataParticleType.CONTROL_RECORD)
        self.assert_data_particle_parameters(data_particle,
                                             self._control_record_parameters,
                                             verify_values)

###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
#                                                                             #
#   These tests are especially useful for testing parsers and other data      #
#   handling.  The tests generally focus on small segments of code, like a    #
#   single function call, but more complex code using Mock objects.  However  #
#   if you find yourself mocking too much maybe it is better as an            #
#   integration test.                                                         #
#                                                                             #
#   Unit tests do not start up external processes like the port agent or      #
#   driver process.                                                           #
###############################################################################
@attr('UNIT', group='mi')
class SamiUnitTest(InstrumentDriverUnitTestCase, SamiMixin):
    pass

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class SamiIntegrationTest(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def assert_particle_count(self, particle_type, particle_count, timeout):
        start_time = time.time()
        end_time = start_time + timeout
        while True:
            num_samples = len(self.get_sample_events(particle_type))
            elapsed = time.time() - start_time
            if num_samples >= particle_count:
                rate = elapsed / num_samples
                log.debug('Found %d samples, elapsed time: %d, approx data rate: %d seconds/sample',
                          num_samples, elapsed, rate)
                break
            # else:
            #    log.debug('Found %d samples of %d expected, elapsed time: %d', num_samples, particle_count, elapsed)
            self.assertGreater(end_time, time.time(), msg="Timeout waiting for sample")
            time.sleep(1)

    ## Have to override because battery and thermistor do not have port time stamps
    def assert_data_particle_header(self, data_particle, stream_name, require_instrument_timestamp=False):
        """
        Verify a data particle header is formatted properly
        @param data_particle version 1 data particle
        @param stream_name version 1 data particle
        @param require_instrument_timestamp should we verify the instrument timestamp exists
        """
        sample_dict = self.convert_data_particle_to_dict(data_particle)
        log.debug("SAMPLEDICT: %s", sample_dict)

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME], stream_name)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID], DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertIsInstance(sample_dict[DataParticleKey.VALUES], list)

        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        self.assertIsNotNone(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP))
        self.assertIsInstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float)

        # It is highly unlikely that we should have a particle without a port agent timestamp,
        # at least that's the current assumption.
        ## self.assertIsNotNone(sample_dict.get(DataParticleKey.PORT_TIMESTAMP))
        ## self.assertIsInstance(sample_dict.get(DataParticleKey.PORT_TIMESTAMP), float)

        if(require_instrument_timestamp):
            self.assertIsNotNone(sample_dict.get(DataParticleKey.INTERNAL_TIMESTAMP))
            self.assertIsInstance(sample_dict.get(DataParticleKey.INTERNAL_TIMESTAMP), float)

    def assert_time_sync(self, status_particle):
        status_dict = self.get_data_particle_values_as_dict(status_particle)
        elapsed_time_config = status_dict.get(SamiRegularStatusDataParticleKey.ELAPSED_TIME_CONFIG)
        current_sami_time = SamiProtocol._current_sami_time()
        log.debug("elapsed_time_config = " + str(elapsed_time_config))
        log.debug("current_sami_time = " + str(current_sami_time))
        time_difference = current_sami_time - elapsed_time_config
        log.debug("time difference = %s" % time_difference)
        sami_now_seconds = current_sami_time - SAMI_UNIX_OFFSET.total_seconds()
        sami_now = datetime.datetime.utcfromtimestamp(sami_now_seconds)
        log.debug('utc time = %s' % datetime.datetime.utcnow())
        log.debug('sami_now = %s' % sami_now)

        self.assertTrue(time_difference <= TIME_THRESHOLD,
                        "Time threshold exceeded, time_difference = %s, time_threshold = %s" % (time_difference, TIME_THRESHOLD))

    def test_time_sync(self):
        self.assert_initialize_driver()
        time.sleep(10)

        self.clear_events()
        request_status_time = time.time()
        self.assert_driver_command(SamiProtocolEvent.ACQUIRE_STATUS)
        self.assert_async_particle_generation(SamiDataParticleType.REGULAR_STATUS, self.assert_time_sync, timeout=10)
        receive_status_time = time.time()
        status_time = receive_status_time - request_status_time
        log.debug("status_time = " + str(status_time))

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class SamiQualificationTest(InstrumentDriverQualificationTestCase):

    ## Have to override because battery and thermistor do not have port time stamps
    def assert_data_particle_header(self, data_particle, stream_name, require_instrument_timestamp=False):
        """
        Verify a data particle header is formatted properly
        @param data_particle version 1 data particle
        @param stream_name version 1 data particle
        @param require_instrument_timestamp should we verify the instrument timestamp exists
        """
        sample_dict = self.convert_data_particle_to_dict(data_particle)
        log.debug("SAMPLEDICT: %s", sample_dict)

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME], stream_name)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID], DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertIsInstance(sample_dict[DataParticleKey.VALUES], list)

        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        self.assertIsNotNone(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP))
        self.assertIsInstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float)

        # It is highly unlikely that we should have a particle without a port agent timestamp,
        # at least that's the current assumption.
        ## self.assertIsNotNone(sample_dict.get(DataParticleKey.PORT_TIMESTAMP))
        ## self.assertIsInstance(sample_dict.get(DataParticleKey.PORT_TIMESTAMP), float)

        if(require_instrument_timestamp):
            self.assertIsNotNone(sample_dict.get(DataParticleKey.INTERNAL_TIMESTAMP))
            self.assertIsInstance(sample_dict.get(DataParticleKey.INTERNAL_TIMESTAMP), float)

    ## Have to override because the driver enters a sample state as soon as autosample mode is entered by design.
    def assert_start_autosample(self, timeout=GO_ACTIVE_TIMEOUT):
        '''
        Enter autosample mode from command
        '''
        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, DriverProtocolState.COMMAND)

        # Begin streaming.
        cmd = AgentCommand(command=DriverEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=timeout)

        # state = self.instrument_agent_client.get_agent_state()
        # self.assertEqual(state, ResourceAgentState.STREAMING)

        self.assert_state_change(ResourceAgentState.STREAMING, SamiProtocolState.AUTOSAMPLE, timeout=timeout)

    ## Have to override because the driver enters a sample state as soon as autosample mode is entered by design.
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
        ## self.assert_enter_command_mode()

        # Begin streaming.
        ## self.assert_start_autosample()

        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, DriverProtocolState.COMMAND)

        # Begin streaming.
        cmd = AgentCommand(command=DriverEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=timeout)

        # Wait for driver to exit sample state
        self.assert_particle_async(sample_queue, sample_data_assert, 1, timeout)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)

        sample_count -= 1
        self.assert_particle_async(sample_queue, sample_data_assert, sample_count, timeout)

        # Halt streaming.
        self.assert_stop_autosample()

    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    ## Not applicable to this driver
    def test_discover(self):
        pass

    def test_boot_prompt_escape(self):

        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        # Erase memory
        self.tcp_client.send_data("E5A%s" % NEWLINE)

        time.sleep(1)

        # Cause boot prompt by entering L5A command without a config string
        self.tcp_client.send_data("L5A%s" % NEWLINE)

        time.sleep(10)

        self.tcp_client.send_data(NEWLINE)

        boot_prompt = self.tcp_client.expect(Prompt.BOOT_PROMPT)
        self.assertTrue(boot_prompt)

        self.assert_direct_access_stop_telnet()

        self.assert_state_change(ResourceAgentState.COMMAND, SamiProtocolState.COMMAND, 60)

