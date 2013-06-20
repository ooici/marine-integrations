"""
@package mi.instrument.teledyne.workhorse_monitor_75_khz.rsn.test.test_driver
@author Roger Unwin
@brief Test cases for rsn driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import socket

import unittest
import time as time
import datetime as dt
from mi.core.time import get_timestamp_delayed

from nose.plugins.attrib import attr
from mock import Mock
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.log import get_logger; log = get_logger()

# MI imports.
from mi.idk.unit_test import AgentCapabilityType
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import DriverStartupConfigKey

from mi.instrument.teledyne.test.test_driver import TeledyneUnitTest
from mi.instrument.teledyne.test.test_driver import TeledyneIntegrationTest
from mi.instrument.teledyne.test.test_driver import TeledyneQualificationTest
from mi.instrument.teledyne.test.test_driver import TeledynePublicationTest

from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import WorkhorseInstrumentDriver

from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import DataParticleType
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import WorkhorseProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import WorkhorseParameter

from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import WorkhorseScheduledJob
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import WorkhorsePrompt
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import NEWLINE

from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_SYSTEM_CONFIGURATION_KEY
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_SYSTEM_CONFIGURATION_DataParticle
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_COMPASS_CALIBRATION_KEY
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_COMPASS_CALIBRATION_DataParticle

#from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import SAMPLE_RAW_DATA 
#from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import CALIBRATION_RAW_DATA
#from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import PS0_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import PS3_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import FD_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import PT200_RAW_DATA

from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException
from pyon.core.exception import Conflict
from pyon.agent.agent import ResourceAgentEvent

from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import ResourceAgentState
from random import randint

from mi.idk.unit_test import AGENT_DISCOVER_TIMEOUT
from mi.idk.unit_test import GO_ACTIVE_TIMEOUT
from mi.idk.unit_test import GET_TIMEOUT
from mi.idk.unit_test import SET_TIMEOUT
from mi.idk.unit_test import EXECUTE_TIMEOUT

from mi.instrument.teledyne.driver import TeledyneParameter as Parameter
from mi.instrument.teledyne.driver import TeledyneProtocolEvent as ProtocolEvent
from mi.instrument.teledyne.driver import TeledyneProtocolState as ProtocolState
from mi.instrument.teledyne.driver import TeledyneScheduledJob as ScheduledJob
from mi.instrument.teledyne.driver import TeledynePrompt as Prompt

#AGENT_DISCOVER_TIMEOUT=3600
#GO_ACTIVE_TIMEOUT=3600 # i have a slow instrument
#GET_TIMEOUT=3000
#SET_TIMEOUT=9000
#EXECUTE_TIMEOUT=3000

#tolerance = 500

# Globals
#raw_stream_received = False
#parsed_stream_received = False






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
############

###############################################################################
#                                UNIT TESTS                                   #
###############################################################################
@attr('UNIT', group='mi')
class WorkhorseDriverUnitTest(TeledyneUnitTest):
    def setUp(self):
        TeledyneUnitTest.setUp(self)


###############################################################################
#                            INTEGRATION TESTS                                #
###############################################################################
@attr('INT', group='mi')
class WorkhorseDriverIntegrationTest(TeledyneIntegrationTest):
    # test if this can pre-set, and be overridden by mixin
    # TODO: does this work
    #

    _tested = {}
    """
    _driver_parameter_defaults = {
        #Parameter.SERIAL_DATA_OUT: None,
        Parameter.INSTRUMENT_ID: 0,
        Parameter.XMIT_POWER: 255,
        Parameter.SPEED_OF_SOUND: 1500,
        Parameter.SALINITY: 35,
        Parameter.COORDINATE_TRANSFORMATION: '11111',
        Parameter.SENSOR_SOURCE: "1111101",
        Parameter.TIME_PER_ENSEMBLE: '00:00:00.00',
        Parameter.TIME_OF_FIRST_PING: None,
        Parameter.TIME_PER_PING: '00:01.00',
        #Parameter.TIME: False,
        Parameter.FALSE_TARGET_THRESHOLD: '050,001',
        Parameter.BANDWIDTH_CONTROL: 0,
        Parameter.CORRELATION_THRESHOLD: 64,
        Parameter.SERIAL_OUT_FW_SWITCHES: '111100000',
        Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
        Parameter.BLANK_AFTER_TRANSMIT: 704,
        Parameter.CLIP_DATA_PAST_BOTTOM: 0,
        Parameter.RECEIVER_GAIN_SELECT: 1,
        Parameter.WATER_REFERENCE_LAYER: '001,005',
        Parameter.WATER_PROFILING_MODE: 1,
        Parameter.NUMBER_OF_DEPTH_CELLS: 100,
        Parameter.PINGS_PER_ENSEMBLE: 1,
        Parameter.DEPTH_CELL_SIZE: 800,
        Parameter.TRANSMIT_LENGTH: 0,
        Parameter.PING_WEIGHT: 0,
        Parameter.AMBIGUITY_VELOCITY: 175,
    }
    """
    def setUp(self):
        TeledyneIntegrationTest.setUp(self)

    def assert_compass_calibration(self):
        """
        Verify a calibration particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.ADCP_COMPASS_CALIBRATION, self.assert_particle_compass_calibration, timeout=700)

    def assert_acquire_status(self):
        """
        Verify a status particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.ADCP_SYSTEM_CONFIGURATION, self.assert_particle_system_configuration, timeout=300)

    ###
    #    Add instrument specific integration tests
    ###
    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply, True)

    def test_commands(self):
        """
        Run instrument commands from both command and streaming mode.
        """
        self.assert_initialize_driver()
        ####
        # First test in command mode
        ####

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        self.assert_driver_command(ProtocolEvent.GET_CALIBRATION)
        self.assert_driver_command(ProtocolEvent.GET_CONFIGURATION)

        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.SEND_LAST_SAMPLE, regex='^\x7f\x7fh.*')
        self.assert_driver_command(ProtocolEvent.SAVE_SETUP_TO_RAM, expected="Parameters saved as USER defaults")
        self.assert_driver_command(ProtocolEvent.GET_ERROR_STATUS_WORD, regex='^........')
        self.assert_driver_command(ProtocolEvent.CLEAR_ERROR_STATUS_WORD, regex='^Error Status Word Cleared')
        self.assert_driver_command(ProtocolEvent.GET_FAULT_LOG, regex='^Total Unique Faults   =.*')
        self.assert_driver_command(ProtocolEvent.CLEAR_FAULT_LOG, expected='FC ..........\r\n Fault Log Cleared.\r\nClearing buffer @0x00801000\r\nDone [i=2048].\r\n')
        self.assert_driver_command(ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, regex='^Beam Width:')
        self.assert_driver_command(ProtocolEvent.RUN_TEST_200, regex='^  Ambient  Temperature =')

        ####
        # Test in streaming mode
        ####
        # Put us in streaming
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command_exception(ProtocolEvent.SEND_LAST_SAMPLE, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.SAVE_SETUP_TO_RAM, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.GET_ERROR_STATUS_WORD, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.CLEAR_ERROR_STATUS_WORD, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.GET_FAULT_LOG, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.CLEAR_FAULT_LOG, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.RUN_TEST_200, exception_class=InstrumentCommandException)
        self.assert_driver_command(ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command_exception(ProtocolEvent.CLOCK_SYNC, exception_class=InstrumentCommandException)
        self.assert_driver_command(ProtocolEvent.GET_CALIBRATION, regex=r'Calibration date and time:')
        self.assert_driver_command(ProtocolEvent.GET_CONFIGURATION, regex=r' Instrument S/N')
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)


    # This needs reworking...

    def test_startup_params(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.

        since nose orders the tests by ascii value this should run first.
        """
        log.error("BEFORE INITIALZIE")
        self.assert_initialize_driver()
        log.error("AFTER INITIALZIE")

        """
        get_values = {
            #Parameter.SERIAL_FLOW_CONTROL: '11110',
            #Parameter.BANNER: False,
            Parameter.INSTRUMENT_ID: 0,
            #Parameter.SLEEP_ENABLE: 0,
            #Parameter.SAVE_NVRAM_TO_RECORDER: True,
            #Parameter.POLLED_MODE: False,
            Parameter.XMIT_POWER: 255,
            Parameter.SPEED_OF_SOUND: 1500,
            #Parameter.PITCH: 0,
            #Parameter.ROLL: 0,
            Parameter.SALINITY: 35,
            Parameter.TIME_PER_ENSEMBLE: '00:00:00.00',
            Parameter.TIME_PER_PING: '00:01.00',
            Parameter.FALSE_TARGET_THRESHOLD: '050,001',
            #Parameter.BANDWIDTH_CONTROL: 0,
            Parameter.CORRELATION_THRESHOLD: 64,
            Parameter.SERIAL_OUT_FW_SWITCHES: '111100000',
            Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
            #Parameter.BLANK_AFTER_TRANSMIT: 704,
            Parameter.CLIP_DATA_PAST_BOTTOM: 0,
            Parameter.RECEIVER_GAIN_SELECT: 1,
            Parameter.WATER_REFERENCE_LAYER: '001,005',
            Parameter.WATER_PROFILING_MODE: 1,
            Parameter.NUMBER_OF_DEPTH_CELLS: 100,
            Parameter.PINGS_PER_ENSEMBLE: 1,
            Parameter.DEPTH_CELL_SIZE: 800,
            Parameter.TRANSMIT_LENGTH: 0,
            Parameter.PING_WEIGHT: 0,
            Parameter.AMBIGUITY_VELOCITY: 175,
        }
        Should be able to use the _driver_parameter_defaults instead of aboev
        """
        get_values = self._driver_parameter_defaults

        # Change the values of these parameters to something before the
        # driver is reinitalized.  They should be blown away on reinit.
        new_values = {
            Parameter.INSTRUMENT_ID: 1,
            Parameter.XMIT_POWER: 250,
            Parameter.SPEED_OF_SOUND: 1400,
            Parameter.SALINITY: 37,
            Parameter.COORDINATE_TRANSFORMATION: '11111',
            Parameter.SENSOR_SOURCE: "1111101",
            Parameter.TIME_PER_ENSEMBLE: '00:01:00.00',
            Parameter.TIME_PER_PING: '00:02.00',
            Parameter.FALSE_TARGET_THRESHOLD: '051,002',
            #RO#Parameter.BANDWIDTH_CONTROL: 1,
            Parameter.CORRELATION_THRESHOLD: 60,
            #RO#Parameter.SERIAL_OUT_FW_SWITCHES: '101010101',
            Parameter.ERROR_VELOCITY_THRESHOLD: 1900,
            #RO#Parameter.BLANK_AFTER_TRANSMIT: 710,
            Parameter.CLIP_DATA_PAST_BOTTOM: 1,
            Parameter.RECEIVER_GAIN_SELECT: 0,
            Parameter.WATER_REFERENCE_LAYER: '002,006',
            #RO#Parameter.WATER_PROFILING_MODE: 0,
            Parameter.NUMBER_OF_DEPTH_CELLS: 80,
            Parameter.PINGS_PER_ENSEMBLE: 2,
            Parameter.DEPTH_CELL_SIZE: 600,
            Parameter.TRANSMIT_LENGTH: 1,
            Parameter.PING_WEIGHT: 1,
            Parameter.AMBIGUITY_VELOCITY: 100,
        }
        """
            Parameter.INSTRUMENT_ID: 1,
            #Parameter.SLEEP_ENABLE: 1,
            #Parameter.POLLED_MODE: True,
            Parameter.XMIT_POWER: 250,
            Parameter.SPEED_OF_SOUND: 1400,
            #Parameter.PITCH: 1,
            #Parameter.ROLL: 1,
            Parameter.SALINITY: 37,
            Parameter.TIME_PER_ENSEMBLE: '00:01:00.00',
            Parameter.TIME_PER_PING: '00:02.00',
            Parameter.FALSE_TARGET_THRESHOLD: '051,001',
            #Parameter.BANDWIDTH_CONTROL: 1,
            Parameter.CORRELATION_THRESHOLD: 60,
            Parameter.ERROR_VELOCITY_THRESHOLD: 1900,
            #Parameter.BLANK_AFTER_TRANSMIT: 710,
            Parameter.CLIP_DATA_PAST_BOTTOM: 1,
            Parameter.RECEIVER_GAIN_SELECT: 0,
            Parameter.WATER_REFERENCE_LAYER: '002,006',
            Parameter.NUMBER_OF_DEPTH_CELLS: 80,
            Parameter.PINGS_PER_ENSEMBLE: 2,
            Parameter.DEPTH_CELL_SIZE: 600,
            Parameter.TRANSMIT_LENGTH: 1,
            Parameter.PING_WEIGHT: 1,
            Parameter.AMBIGUITY_VELOCITY: 100,
        """
        
        
        self.assert_startup_parameters(self.assert_driver_parameters, new_values, get_values)



###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class WorkhorseDriverQualificationTest(TeledyneQualificationTest):
    def setUp(self):
        TeledyneQualificationTest.setUp(self)

    def assert_configuration(self, data_particle, verify_values = False):
        '''
        Verify assert_compass_calibration particle
        @param data_particle:  ADCP_COMPASS_CALIBRATION data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(ADCP_SYSTEM_CONFIGURATION_KEY, self._system_configuration_data_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_SYSTEM_CONFIGURATION)
        self.assert_data_particle_parameters(data_particle, self._system_configuration_data_parameters, verify_values)

    def assert_compass_calibration(self, data_particle, verify_values = False):
        '''
        Verify assert_compass_calibration particle
        @param data_particle:  ADCP_COMPASS_CALIBRATION data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(ADCP_COMPASS_CALIBRATION_KEY, self._calibration_data_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_COMPASS_CALIBRATION)
        self.assert_data_particle_parameters(data_particle, self._calibration_data_parameters, verify_values)

    def test_cycle(self):
        """
        Verify we can bounce between command and streaming.  We try it a few times to see if we can find a timeout.
        """
        self.assert_enter_command_mode()

        self.assert_cycle()
        self.assert_cycle()
        self.assert_cycle()
        self.assert_cycle()

    # need to override this because we are slow and dont feel like modifying the base class lightly
    def assert_set_parameter(self, name, value, verify=True):
        '''
        verify that parameters are set correctly.  Assumes we are in command mode.
        '''
        setParams = { name : value }
        getParams = [ name ]

        self.instrument_agent_client.set_resource(setParams, timeout=300)

        if(verify):
            result = self.instrument_agent_client.get_resource(getParams, timeout=300)
            self.assertEqual(result[name], value)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """

        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.SPEED_OF_SOUND, 1487)

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)

        self.tcp_client.send_data("%sEC1488%s" % (NEWLINE, NEWLINE))

        self.tcp_client.expect(Prompt.COMMAND)

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.SPEED_OF_SOUND, 1488)

    def test_execute_clock_sync(self):
        """
        Verify we can syncronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)

        # Now verify that at least the date matches
        check_new_params = self.instrument_agent_client.get_resource([Parameter.TIME], timeout=300)

        instrument_time = time.mktime(time.strptime(check_new_params.get(Parameter.TIME).lower(), "%Y/%m/%d,%H:%M:%S %Z"))

        self.assertLessEqual(abs(instrument_time - time.mktime(time.gmtime())), 15)

    # this will probably need to move up to the leaf level.
    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.

        TODO: seems this should derive from _driver_capabilities in mixin
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                ProtocolEvent.CLOCK_SYNC,
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.CLEAR_ERROR_STATUS_WORD,
                ProtocolEvent.CLEAR_FAULT_LOG,
                ProtocolEvent.GET_CALIBRATION,
                ProtocolEvent.GET_CONFIGURATION,
                ProtocolEvent.GET_ERROR_STATUS_WORD,
                ProtocolEvent.GET_FAULT_LOG,
                ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX,
                ProtocolEvent.RUN_TEST_200,
                ProtocolEvent.SAVE_SETUP_TO_RAM,
                ProtocolEvent.SEND_LAST_SAMPLE
                ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            ProtocolEvent.STOP_AUTOSAMPLE,
            ProtocolEvent.GET_CONFIGURATION,
            ProtocolEvent.GET_CALIBRATION,
            ]
        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        ##################
        #  DA Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = self._common_da_resource_commands()

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

    def test_startup_params_first_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.SERIAL_FLOW_CONTROL, '11110') # Immutable
        self.assert_get_parameter(Parameter.BANNER, False)
        self.assert_get_parameter(Parameter.INSTRUMENT_ID, 0)
        self.assert_get_parameter(Parameter.SLEEP_ENABLE, 0)
        self.assert_get_parameter(Parameter.SAVE_NVRAM_TO_RECORDER, True) # Immutable
        self.assert_get_parameter(Parameter.POLLED_MODE, False)
        self.assert_get_parameter(Parameter.XMIT_POWER, 255)
        self.assert_get_parameter(Parameter.SPEED_OF_SOUND, 1500)
        self.assert_get_parameter(Parameter.PITCH, 0)
        self.assert_get_parameter(Parameter.ROLL, 0)
        self.assert_get_parameter(Parameter.SALINITY, 35)
        self.assert_get_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:00.00')
        self.assert_get_parameter(Parameter.TIME_PER_PING, '00:01.00')
        self.assert_get_parameter(Parameter.FALSE_TARGET_THRESHOLD, '050,001')
        self.assert_get_parameter(Parameter.BANDWIDTH_CONTROL, 0)
        self.assert_get_parameter(Parameter.CORRELATION_THRESHOLD, 64)
        self.assert_get_parameter(Parameter.SERIAL_OUT_FW_SWITCHES, '111100000') # Immutable
        self.assert_get_parameter(Parameter.ERROR_VELOCITY_THRESHOLD, 2000)
        self.assert_get_parameter(Parameter.BLANK_AFTER_TRANSMIT, 704)
        self.assert_get_parameter(Parameter.CLIP_DATA_PAST_BOTTOM, 0)
        self.assert_get_parameter(Parameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_get_parameter(Parameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_get_parameter(Parameter.WATER_PROFILING_MODE, 1) # Immutable
        self.assert_get_parameter(Parameter.NUMBER_OF_DEPTH_CELLS, 100)
        self.assert_get_parameter(Parameter.PINGS_PER_ENSEMBLE, 1)
        self.assert_get_parameter(Parameter.DEPTH_CELL_SIZE, 800)
        self.assert_get_parameter(Parameter.TRANSMIT_LENGTH, 0)
        self.assert_get_parameter(Parameter.PING_WEIGHT, 0)
        self.assert_get_parameter(Parameter.AMBIGUITY_VELOCITY, 175)

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(Parameter.INSTRUMENT_ID, 1)
        self.assert_set_parameter(Parameter.SLEEP_ENABLE, 1)
        self.assert_set_parameter(Parameter.POLLED_MODE, True)
        self.assert_set_parameter(Parameter.XMIT_POWER, 250)
        self.assert_set_parameter(Parameter.SPEED_OF_SOUND, 1480)
        self.assert_set_parameter(Parameter.PITCH, 1)
        self.assert_set_parameter(Parameter.ROLL, 1)
        self.assert_set_parameter(Parameter.SALINITY, 36)
        self.assert_set_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:01.00')
        self.assert_set_parameter(Parameter.TIME_PER_PING, '00:02.00')
        self.assert_set_parameter(Parameter.FALSE_TARGET_THRESHOLD, '049,002')
        self.assert_set_parameter(Parameter.BANDWIDTH_CONTROL, 1)
        self.assert_set_parameter(Parameter.CORRELATION_THRESHOLD, 63)
        self.assert_set_parameter(Parameter.ERROR_VELOCITY_THRESHOLD, 1999)
        self.assert_set_parameter(Parameter.BLANK_AFTER_TRANSMIT, 714)
        self.assert_set_parameter(Parameter.CLIP_DATA_PAST_BOTTOM, 1)
        self.assert_set_parameter(Parameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set_parameter(Parameter.WATER_REFERENCE_LAYER, '002,006')
        self.assert_set_parameter(Parameter.NUMBER_OF_DEPTH_CELLS, 99)
        self.assert_set_parameter(Parameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set_parameter(Parameter.DEPTH_CELL_SIZE, 790)
        self.assert_set_parameter(Parameter.TRANSMIT_LENGTH, 1)
        self.assert_set_parameter(Parameter.PING_WEIGHT, 1)
        self.assert_set_parameter(Parameter.AMBIGUITY_VELOCITY, 176)

    def test_startup_params_second_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.SERIAL_FLOW_CONTROL, '11110') # Immutable
        self.assert_get_parameter(Parameter.BANNER, False)
        self.assert_get_parameter(Parameter.INSTRUMENT_ID, 0)
        self.assert_get_parameter(Parameter.SLEEP_ENABLE, 0)
        self.assert_get_parameter(Parameter.SAVE_NVRAM_TO_RECORDER, True) # Immutable
        self.assert_get_parameter(Parameter.POLLED_MODE, False)
        self.assert_get_parameter(Parameter.XMIT_POWER, 255)
        self.assert_get_parameter(Parameter.SPEED_OF_SOUND, 1500)
        self.assert_get_parameter(Parameter.PITCH, 0)
        self.assert_get_parameter(Parameter.ROLL, 0)
        self.assert_get_parameter(Parameter.SALINITY, 35)
        self.assert_get_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:00.00')
        self.assert_get_parameter(Parameter.TIME_PER_PING, '00:01.00')
        self.assert_get_parameter(Parameter.FALSE_TARGET_THRESHOLD, '050,001')
        self.assert_get_parameter(Parameter.BANDWIDTH_CONTROL, 0)
        self.assert_get_parameter(Parameter.CORRELATION_THRESHOLD, 64)
        self.assert_get_parameter(Parameter.SERIAL_OUT_FW_SWITCHES, '111100000') # Immutable
        self.assert_get_parameter(Parameter.ERROR_VELOCITY_THRESHOLD, 2000)
        self.assert_get_parameter(Parameter.BLANK_AFTER_TRANSMIT, 704)
        self.assert_get_parameter(Parameter.CLIP_DATA_PAST_BOTTOM, 0)
        self.assert_get_parameter(Parameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_get_parameter(Parameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_get_parameter(Parameter.WATER_PROFILING_MODE, 1) # Immutable
        self.assert_get_parameter(Parameter.NUMBER_OF_DEPTH_CELLS, 100)
        self.assert_get_parameter(Parameter.PINGS_PER_ENSEMBLE, 1)
        self.assert_get_parameter(Parameter.DEPTH_CELL_SIZE, 800)
        self.assert_get_parameter(Parameter.TRANSMIT_LENGTH, 0)
        self.assert_get_parameter(Parameter.PING_WEIGHT, 0)
        self.assert_get_parameter(Parameter.AMBIGUITY_VELOCITY, 175)

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(Parameter.INSTRUMENT_ID, 1)
        self.assert_set_parameter(Parameter.SLEEP_ENABLE, 1)
        self.assert_set_parameter(Parameter.POLLED_MODE, True)
        self.assert_set_parameter(Parameter.XMIT_POWER, 250)
        self.assert_set_parameter(Parameter.SPEED_OF_SOUND, 1480)
        self.assert_set_parameter(Parameter.PITCH, 1)
        self.assert_set_parameter(Parameter.ROLL, 1)
        self.assert_set_parameter(Parameter.SALINITY, 36)
        self.assert_set_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:01.00')
        self.assert_set_parameter(Parameter.TIME_PER_PING, '00:02.00')
        self.assert_set_parameter(Parameter.FALSE_TARGET_THRESHOLD, '049,002')
        self.assert_set_parameter(Parameter.BANDWIDTH_CONTROL, 1)
        self.assert_set_parameter(Parameter.CORRELATION_THRESHOLD, 63)
        self.assert_set_parameter(Parameter.ERROR_VELOCITY_THRESHOLD, 1999)
        self.assert_set_parameter(Parameter.BLANK_AFTER_TRANSMIT, 714)
        self.assert_set_parameter(Parameter.CLIP_DATA_PAST_BOTTOM, 1)
        self.assert_set_parameter(Parameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set_parameter(Parameter.WATER_REFERENCE_LAYER, '002,006')
        self.assert_set_parameter(Parameter.NUMBER_OF_DEPTH_CELLS, 99)
        self.assert_set_parameter(Parameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set_parameter(Parameter.DEPTH_CELL_SIZE, 790)
        self.assert_set_parameter(Parameter.TRANSMIT_LENGTH, 1)
        self.assert_set_parameter(Parameter.PING_WEIGHT, 1)
        self.assert_set_parameter(Parameter.AMBIGUITY_VELOCITY, 176)


###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific pulication tests are for                                    #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class WorkhorseDriverPublicationTest(TeledynePublicationTest):
    def setUp(self):
        TeledynePublicationTest.setUp(self)

    def test_granule_generation(self):
        self.assert_initialize_driver()

        # Currently these tests only verify that the data granule is generated, but the values
        # are not tested.  We will eventually need to replace log.debug with a better callback
        # function that actually tests the granule.
        self.assert_sample_async("raw data", log.debug, DataParticleType.RAW, timeout=10)
        self.assert_sample_async(SAMPLE_RAW_DATA, log.debug, DataParticleType.ADCP_PD0_PARSED_BEAM, timeout=10)
        self.assert_sample_async(PS0_RAW_DATA, log.debug, DataParticleType.ADCP_SYSTEM_CONFIGURATION, timeout=10)
        self.assert_sample_async(CALIBRATION_RAW_DATA, log.debug, DataParticleType.ADCP_COMPASS_CALIBRATION, timeout=10)
