"""
@package mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_driver
@author Roger Unwin
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

from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import WorkhorseInstrumentDriver

from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import DataParticleType
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import TeledyneProtocolState
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import TeledyneProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import WorkhorseParameter

from mi.instrument.teledyne.driver import TeledyneScheduledJob
from mi.instrument.teledyne.test.test_driver import TeledyneParameterAltValue
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import TeledynePrompt
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import NEWLINE

from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_SYSTEM_CONFIGURATION_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_SYSTEM_CONFIGURATION_DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_COMPASS_CALIBRATION_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_COMPASS_CALIBRATION_DataParticle

#from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import PS3_RAW_DATA
#from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import FD_RAW_DATA
#from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import PT200_RAW_DATA

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

class WorkhorseParameterAltValue(TeledyneParameterAltValue):
    # Values that are valid, but not the ones we want to use,
    # used for testing to verify that we are setting good values.
    #

    # Probably best NOT to tweek this one.
    SERIAL_FLOW_CONTROL = '11110' 
    BANNER = 1
    SAVE_NVRAM_TO_RECORDER = True # Immutable.
    SLEEP_ENABLE = 1
    POLLED_MODE = True
    PITCH = 1
    ROLL = 1



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

    def setUp(self):
        TeledyneIntegrationTest.setUp(self)
        """
        for k in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[k]:
                if self._driver_parameters[k][self.READONLY] == False:
                    self._driver_parameter_defaults[k] = self._driver_parameters[k][self.VALUE]
        """
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
        reply = self.driver_client.cmd_dvr('get_resource', WorkhorseParameter.ALL)
        self.assert_driver_parameters(reply, True)


    def test_commands(self):
        """
        Run instrument commands from both command and streaming mode.
        """
        self.assert_initialize_driver()
        ####
        # First test in command mode
        ####

        self.assert_driver_command(TeledyneProtocolEvent.START_AUTOSAMPLE, state=TeledyneProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE, state=TeledyneProtocolState.COMMAND, delay=1)

        self.assert_driver_command(TeledyneProtocolEvent.GET_CALIBRATION)
        self.assert_driver_command(TeledyneProtocolEvent.GET_CONFIGURATION)
        self.assert_driver_command(TeledyneProtocolEvent.CLOCK_SYNC)
        self.assert_driver_command(TeledyneProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command(TeledyneProtocolEvent.SEND_LAST_SAMPLE, regex='^\x7f\x7f.*')
        self.assert_driver_command(TeledyneProtocolEvent.SAVE_SETUP_TO_RAM, expected="Parameters saved as USER defaults")
        self.assert_driver_command(TeledyneProtocolEvent.GET_ERROR_STATUS_WORD, regex='^........')
        self.assert_driver_command(TeledyneProtocolEvent.CLEAR_ERROR_STATUS_WORD, regex='^Error Status Word Cleared')
        self.assert_driver_command(TeledyneProtocolEvent.GET_FAULT_LOG, regex='^Total Unique Faults   =.*')
        self.assert_driver_command(TeledyneProtocolEvent.CLEAR_FAULT_LOG, expected='FC ..........\r\n Fault Log Cleared.\r\nClearing buffer @0x00801000\r\nDone [i=2048].\r\n')
        self.assert_driver_command(TeledyneProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, regex='^Beam Width:')
        self.assert_driver_command(TeledyneProtocolEvent.RUN_TEST_200, regex='^  Ambient  Temperature =')

        ####
        # Test in streaming mode
        ####
        # Put us in streaming
        self.assert_driver_command(TeledyneProtocolEvent.START_AUTOSAMPLE, state=TeledyneProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command_exception(TeledyneProtocolEvent.SEND_LAST_SAMPLE, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.SAVE_SETUP_TO_RAM, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.GET_ERROR_STATUS_WORD, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.CLEAR_ERROR_STATUS_WORD, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.GET_FAULT_LOG, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.CLEAR_FAULT_LOG, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.RUN_TEST_200, exception_class=InstrumentCommandException)
        self.assert_driver_command(TeledyneProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command_exception(TeledyneProtocolEvent.CLOCK_SYNC, exception_class=InstrumentCommandException)
        self.assert_driver_command(TeledyneProtocolEvent.GET_CALIBRATION, regex=r'Calibration date and time:')
        self.assert_driver_command(TeledyneProtocolEvent.GET_CONFIGURATION, regex=r' Instrument S/N')
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE, state=TeledyneProtocolState.COMMAND, delay=1)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

    def test_startup_params(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.

        since nose orders the tests by ascii value this should run first.
        """
        self.assert_initialize_driver()

        get_values = {
            WorkhorseParameter.SERIAL_FLOW_CONTROL: '11110',
            WorkhorseParameter.BANNER: False,
            WorkhorseParameter.INSTRUMENT_ID: 0,
            WorkhorseParameter.SLEEP_ENABLE: 0,
            WorkhorseParameter.SAVE_NVRAM_TO_RECORDER: True,
            WorkhorseParameter.POLLED_MODE: False,
            WorkhorseParameter.XMIT_POWER: 255,
            WorkhorseParameter.SPEED_OF_SOUND: 1485,
            WorkhorseParameter.PITCH: 0,
            WorkhorseParameter.ROLL: 0,
            WorkhorseParameter.SALINITY: 35,
            WorkhorseParameter.TIME_PER_ENSEMBLE: '00:00:00.00',
            WorkhorseParameter.TIME_PER_PING: '00:01.00',
            WorkhorseParameter.FALSE_TARGET_THRESHOLD: '050,001',
            WorkhorseParameter.BANDWIDTH_CONTROL: 0,
            WorkhorseParameter.CORRELATION_THRESHOLD: 64,
            WorkhorseParameter.SERIAL_OUT_FW_SWITCHES: '111100000',
            WorkhorseParameter.ERROR_VELOCITY_THRESHOLD: 2000,
            WorkhorseParameter.BLANK_AFTER_TRANSMIT: 704,
            WorkhorseParameter.CLIP_DATA_PAST_BOTTOM: 0,
            WorkhorseParameter.RECEIVER_GAIN_SELECT: 1,
            WorkhorseParameter.WATER_REFERENCE_LAYER: '001,005',
            WorkhorseParameter.WATER_PROFILING_MODE: 1,
            WorkhorseParameter.NUMBER_OF_DEPTH_CELLS: 100,
            WorkhorseParameter.PINGS_PER_ENSEMBLE: 1,
            WorkhorseParameter.DEPTH_CELL_SIZE: 800,
            WorkhorseParameter.TRANSMIT_LENGTH: 0,
            WorkhorseParameter.PING_WEIGHT: 0,
            WorkhorseParameter.AMBIGUITY_VELOCITY: 175,
        }

        # Change the values of these parameters to something before the
        # driver is reinitalized.  They should be blown away on reinit.
        new_values = {}
      
        p = WorkhorseParameter.dict()
        for k, v in WorkhorseParameterAltValue.dict().items():
            if k not in ('BANNER', 'SERIAL_FLOW_CONTROL', 'SAVE_NVRAM_TO_RECORDER'):
                new_values[p[k]] = v
        self.assert_startup_parameters(self.assert_driver_parameters, new_values, get_values)



    ###
    #   Test scheduled events
    ###
    def assert_compass_calibration(self):
        """
        Verify a calibration particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.ADCP_COMPASS_CALIBRATION, self.assert_particle_compass_calibration, timeout=120)

    def test_scheduled_compass_calibration_command(self):
        """
        Verify the device configuration command can be triggered and run in command
        """
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CALIBRATION, self.assert_compass_calibration, delay=100)
        self.assert_current_state(TeledyneProtocolState.COMMAND)

    def test_scheduled_compass_calibration_autosample(self):
        """
        Verify the device configuration command can be triggered and run in autosample
        """

        self.assert_scheduled_event(TeledyneScheduledJob.GET_CALIBRATION, self.assert_compass_calibration, delay=100,
            autosample_command=TeledyneProtocolEvent.START_AUTOSAMPLE)
        self.assert_current_state(TeledyneProtocolState.AUTOSAMPLE)
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE)

    def assert_acquire_status(self):
        """
        Verify a status particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.ADCP_SYSTEM_CONFIGURATION, self.assert_particle_system_configuration, timeout=120)

    def test_scheduled_device_configuration_command(self):
        """
        Verify the device status command can be triggered and run in command
        """
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CONFIGURATION, self.assert_acquire_status, delay=100)
        self.assert_current_state(TeledyneProtocolState.COMMAND)

    def test_scheduled_device_configuration_autosample(self):
        """
        Verify the device status command can be triggered and run in autosample
        """
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CONFIGURATION, self.assert_acquire_status,
                                    autosample_command=TeledyneProtocolEvent.START_AUTOSAMPLE, delay=100)
        self.assert_current_state(TeledyneProtocolState.AUTOSAMPLE)
        time.sleep(5)
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE)

    def assert_clock_sync(self):
        """
        Verify the clock is set to at least the current date
        """
        dt = self.assert_get(WorkhorseParameter.TIME)
        lt = time.strftime("%Y/%m/%d,%H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        self.assertTrue(lt[:13].upper() in dt.upper())

    def test_scheduled_clock_sync_command(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        self.assert_scheduled_event(TeledyneScheduledJob.CLOCK_SYNC, self.assert_clock_sync, delay=90)
        self.assert_current_state(TeledyneProtocolState.COMMAND)

    def test_scheduled_clock_sync_autosample(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """

        self.assert_scheduled_event(TeledyneScheduledJob.CLOCK_SYNC, self.assert_clock_sync,
                                    autosample_command=TeledyneProtocolEvent.START_AUTOSAMPLE, delay=200)
        self.assert_current_state(TeledyneProtocolState.AUTOSAMPLE)
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE)

    def _test_set_serial_flow_control_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SERIAL_FLOW_CONTROL ======")

        # Test read only raise exceptions on set.
        self.assert_set_exception(WorkhorseParameter.SERIAL_FLOW_CONTROL, '10110')
        self._tested[WorkhorseParameter.SERIAL_FLOW_CONTROL] = True

    def _test_set_save_nvram_to_recorder_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SAVE_NVRAM_TO_RECORDER ======")

        # Test read only raise exceptions on set.
        self.assert_set_exception(WorkhorseParameter.SAVE_NVRAM_TO_RECORDER, False)
        self._tested[WorkhorseParameter.SAVE_NVRAM_TO_RECORDER] = True

    def _test_set_banner_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for BANNER ======")

        # Test read only raise exceptions on set.
        self.assert_set_exception(WorkhorseParameter.BANNER, True)
        self._tested[WorkhorseParameter.BANNER] = True

    def _test_set_pitch(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for PITCH ======")

        # PITCH:  -- Int -6000 to 6000
        self.assert_set(WorkhorseParameter.PITCH, -6000)
        self.assert_set(WorkhorseParameter.PITCH, -4000)
        self.assert_set(WorkhorseParameter.PITCH, -2000)
        self.assert_set(WorkhorseParameter.PITCH, -1)
        self.assert_set(WorkhorseParameter.PITCH, 0)
        self.assert_set(WorkhorseParameter.PITCH, 1)
        self.assert_set(WorkhorseParameter.PITCH, 2000)
        self.assert_set(WorkhorseParameter.PITCH, 4000)
        self.assert_set(WorkhorseParameter.PITCH, 6000)

        self.assert_set_exception(WorkhorseParameter.PITCH, "LEROY JENKINS")
        self.assert_set_exception(WorkhorseParameter.PITCH, -6001)
        self.assert_set_exception(WorkhorseParameter.PITCH, 6001)
        self.assert_set_exception(WorkhorseParameter.PITCH, 3.1415926)

        #
        # Reset to good value.
        #
        #self.assert_set(WorkhorseParameter.PITCH, self._driver_parameter_defaults[WorkhorseParameter.PITCH])
        self.assert_set(WorkhorseParameter.PITCH, self._driver_parameters[WorkhorseParameter.PITCH][self.VALUE])

        self._tested[WorkhorseParameter.PITCH] = True

    def _test_set_roll(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for ROLL ======")

        # ROLL:  -- Int -6000 to 6000
        self.assert_set(WorkhorseParameter.ROLL, -6000)
        self.assert_set(WorkhorseParameter.ROLL, -4000)
        self.assert_set(WorkhorseParameter.ROLL, -2000)
        self.assert_set(WorkhorseParameter.ROLL, -1)
        self.assert_set(WorkhorseParameter.ROLL, 0)
        self.assert_set(WorkhorseParameter.ROLL, 1)
        self.assert_set(WorkhorseParameter.ROLL, 2000)
        self.assert_set(WorkhorseParameter.ROLL, 4000)
        self.assert_set(WorkhorseParameter.ROLL, 6000)

        self.assert_set_exception(WorkhorseParameter.ROLL, "LEROY JENKINS")
        self.assert_set_exception(WorkhorseParameter.ROLL, -6001)
        self.assert_set_exception(WorkhorseParameter.ROLL, 6001)
        self.assert_set_exception(WorkhorseParameter.ROLL, 3.1415926)
        #
        # Reset to good value.
        #
        #self.assert_set(WorkhorseParameter.ROLL, self._driver_parameter_defaults[WorkhorseParameter.ROLL])
        self.assert_set(WorkhorseParameter.ROLL, self._driver_parameters[WorkhorseParameter.ROLL][self.VALUE])
        self._tested[WorkhorseParameter.ROLL] = True

    def _test_set_polled_mode(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for POLLED_MODE ======")
 
        # POLLED_MODE:  -- (True/False)
        self.assert_set(WorkhorseParameter.POLLED_MODE, True)
        self.assert_set_exception(WorkhorseParameter.POLLED_MODE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        #self.assert_set(WorkhorseParameter.POLLED_MODE, self._driver_parameter_defaults[WorkhorseParameter.POLLED_MODE])
        self.assert_set(WorkhorseParameter.POLLED_MODE, self._driver_parameters[WorkhorseParameter.POLLED_MODE][self.VALUE])
        self._tested[WorkhorseParameter.POLLED_MODE] = True

    def _test_set_sleep_enable(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SLEEP_ENABLE ======")

        # SLEEP_ENABLE:  -- (0,1,2)
        self.assert_set(WorkhorseParameter.SLEEP_ENABLE, 1)
        self.assert_set(WorkhorseParameter.SLEEP_ENABLE, 2)

        self.assert_set_exception(WorkhorseParameter.SLEEP_ENABLE, -1)
        self.assert_set_exception(WorkhorseParameter.SLEEP_ENABLE, 3)
        self.assert_set_exception(WorkhorseParameter.SLEEP_ENABLE, 3.1415926)
        self.assert_set_exception(WorkhorseParameter.SLEEP_ENABLE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        #self.assert_set(WorkhorseParameter.SLEEP_ENABLE, self._driver_parameter_defaults[WorkhorseParameter.SLEEP_ENABLE])
        self.assert_set(WorkhorseParameter.SLEEP_ENABLE, self._driver_parameters[WorkhorseParameter.SLEEP_ENABLE][self.VALUE])
        self._tested[WorkhorseParameter.SLEEP_ENABLE] = True

    def _test_set_coordinate_transformation(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for COORDINATE_TRANSFORMATION ======")

        # COORDINATE_TRANSFORMATION:  -- (5 bits 0 or 1)
        self.assert_set(WorkhorseParameter.COORDINATE_TRANSFORMATION, '11000')
        self.assert_set(WorkhorseParameter.COORDINATE_TRANSFORMATION, '11111')
        self.assert_set(WorkhorseParameter.COORDINATE_TRANSFORMATION, '11101')

        self.assert_set(WorkhorseParameter.COORDINATE_TRANSFORMATION, '00000')
        self.assert_set(WorkhorseParameter.COORDINATE_TRANSFORMATION, '00111')
        self.assert_set(WorkhorseParameter.COORDINATE_TRANSFORMATION, '00101')

        self.assert_set_exception(WorkhorseParameter.COORDINATE_TRANSFORMATION, -1)
        self.assert_set_exception(WorkhorseParameter.COORDINATE_TRANSFORMATION, 3)
        self.assert_set_exception(WorkhorseParameter.COORDINATE_TRANSFORMATION, 3.1415926)
        self.assert_set_exception(WorkhorseParameter.COORDINATE_TRANSFORMATION, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        #self.assert_set(WorkhorseParameter.COORDINATE_TRANSFORMATION, self._driver_parameter_defaults[WorkhorseParameter.COORDINATE_TRANSFORMATION])
        self.assert_set(WorkhorseParameter.COORDINATE_TRANSFORMATION, self._driver_parameters[WorkhorseParameter.COORDINATE_TRANSFORMATION][self.VALUE])
        self._tested[WorkhorseParameter.COORDINATE_TRANSFORMATION] = True

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
        self.assert_set_parameter(WorkhorseParameter.SPEED_OF_SOUND, 1487)

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)

        self.tcp_client.send_data("%sEC1488%s" % (NEWLINE, NEWLINE))

        self.tcp_client.expect(TeledynePrompt.COMMAND)

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()

        self.assert_get_parameter(WorkhorseParameter.SPEED_OF_SOUND, 1488)

    def test_execute_clock_sync(self):
        """
        Verify we can syncronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        self.assert_execute_resource(TeledyneProtocolEvent.CLOCK_SYNC)

        # Now verify that at least the date matches
        check_new_params = self.instrument_agent_client.get_resource([WorkhorseParameter.TIME], timeout=45)

        instrument_time = time.mktime(time.strptime(check_new_params.get(WorkhorseParameter.TIME).lower(), "%Y/%m/%d,%H:%M:%S %Z"))

        self.assertLessEqual(abs(instrument_time - time.mktime(time.gmtime())), 45)

    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                TeledyneProtocolEvent.CLOCK_SYNC,
                TeledyneProtocolEvent.START_AUTOSAMPLE,
                TeledyneProtocolEvent.CLEAR_ERROR_STATUS_WORD,
                TeledyneProtocolEvent.CLEAR_FAULT_LOG,
                TeledyneProtocolEvent.GET_CALIBRATION,
                TeledyneProtocolEvent.GET_CONFIGURATION,
                TeledyneProtocolEvent.GET_ERROR_STATUS_WORD,
                TeledyneProtocolEvent.GET_FAULT_LOG,
                TeledyneProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX,
                TeledyneProtocolEvent.RUN_TEST_200,
                TeledyneProtocolEvent.SAVE_SETUP_TO_RAM,
                TeledyneProtocolEvent.SEND_LAST_SAMPLE
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
            TeledyneProtocolEvent.STOP_AUTOSAMPLE,
            TeledyneProtocolEvent.GET_CONFIGURATION,
            TeledyneProtocolEvent.GET_CALIBRATION,
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


        for k in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[k]:
                if False == self._driver_parameters[k][self.READONLY]:
                    self.assert_get_parameter(k, self._driver_parameters[k][self.VALUE])
                    log.error("VERIFYING %s is set to %s appropriately ", k, str(self._driver_parameters[k][self.VALUE]))


        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(WorkhorseParameter.INSTRUMENT_ID, 1)
        self.assert_set_parameter(WorkhorseParameter.SLEEP_ENABLE, 1)
        self.assert_set_parameter(WorkhorseParameter.POLLED_MODE, True)
        self.assert_set_parameter(WorkhorseParameter.XMIT_POWER, 250)
        self.assert_set_parameter(WorkhorseParameter.SPEED_OF_SOUND, 1480)
        self.assert_set_parameter(WorkhorseParameter.PITCH, 1)
        self.assert_set_parameter(WorkhorseParameter.ROLL, 1)
        self.assert_set_parameter(WorkhorseParameter.SALINITY, 36)
        self.assert_set_parameter(WorkhorseParameter.TIME_PER_ENSEMBLE, '00:00:01.00')
        self.assert_set_parameter(WorkhorseParameter.TIME_PER_PING, '00:02.00')
        self.assert_set_parameter(WorkhorseParameter.FALSE_TARGET_THRESHOLD, '049,002')
        self.assert_set_parameter(WorkhorseParameter.BANDWIDTH_CONTROL, 1)
        self.assert_set_parameter(WorkhorseParameter.CORRELATION_THRESHOLD, 63)
        self.assert_set_parameter(WorkhorseParameter.ERROR_VELOCITY_THRESHOLD, 1999)
        self.assert_set_parameter(WorkhorseParameter.BLANK_AFTER_TRANSMIT, 714)
        self.assert_set_parameter(WorkhorseParameter.CLIP_DATA_PAST_BOTTOM, 1)
        self.assert_set_parameter(WorkhorseParameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set_parameter(WorkhorseParameter.WATER_REFERENCE_LAYER, '002,006')
        self.assert_set_parameter(WorkhorseParameter.NUMBER_OF_DEPTH_CELLS, 99)
        self.assert_set_parameter(WorkhorseParameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set_parameter(WorkhorseParameter.DEPTH_CELL_SIZE, 790)
        self.assert_set_parameter(WorkhorseParameter.TRANSMIT_LENGTH, 1)
        self.assert_set_parameter(WorkhorseParameter.PING_WEIGHT, 1)
        self.assert_set_parameter(WorkhorseParameter.AMBIGUITY_VELOCITY, 176)

    def test_startup_params_second_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()
        for k in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[k]:
                if False == self._driver_parameters[k][self.READONLY]:
                    self.assert_get_parameter(k, self._driver_parameters[k][self.VALUE])
                    log.error("VERIFYING %s is set to %s appropriately ", k, str(self._driver_parameters[k][self.VALUE]))

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(WorkhorseParameter.INSTRUMENT_ID, 1)
        self.assert_set_parameter(WorkhorseParameter.SLEEP_ENABLE, 1)
        self.assert_set_parameter(WorkhorseParameter.POLLED_MODE, True)
        self.assert_set_parameter(WorkhorseParameter.XMIT_POWER, 250)
        self.assert_set_parameter(WorkhorseParameter.SPEED_OF_SOUND, 1480)
        self.assert_set_parameter(WorkhorseParameter.PITCH, 1)
        self.assert_set_parameter(WorkhorseParameter.ROLL, 1)
        self.assert_set_parameter(WorkhorseParameter.SALINITY, 36)
        self.assert_set_parameter(WorkhorseParameter.TIME_PER_ENSEMBLE, '00:00:01.00')
        self.assert_set_parameter(WorkhorseParameter.TIME_PER_PING, '00:02.00')
        self.assert_set_parameter(WorkhorseParameter.FALSE_TARGET_THRESHOLD, '049,002')
        self.assert_set_parameter(WorkhorseParameter.BANDWIDTH_CONTROL, 1)
        self.assert_set_parameter(WorkhorseParameter.CORRELATION_THRESHOLD, 63)
        self.assert_set_parameter(WorkhorseParameter.ERROR_VELOCITY_THRESHOLD, 1999)
        self.assert_set_parameter(WorkhorseParameter.BLANK_AFTER_TRANSMIT, 714)
        self.assert_set_parameter(WorkhorseParameter.CLIP_DATA_PAST_BOTTOM, 1)
        self.assert_set_parameter(WorkhorseParameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set_parameter(WorkhorseParameter.WATER_REFERENCE_LAYER, '002,006')
        self.assert_set_parameter(WorkhorseParameter.NUMBER_OF_DEPTH_CELLS, 99)
        self.assert_set_parameter(WorkhorseParameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set_parameter(WorkhorseParameter.DEPTH_CELL_SIZE, 790)
        self.assert_set_parameter(WorkhorseParameter.TRANSMIT_LENGTH, 1)
        self.assert_set_parameter(WorkhorseParameter.PING_WEIGHT, 1)
        self.assert_set_parameter(WorkhorseParameter.AMBIGUITY_VELOCITY, 176)


###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific pulication tests are for                                    #
# testing device specific capabilities                                        #
###############################################################################

@attr('PUB', group='mi')
class WorkhorseDriverPublicationTest(TeledynePublicationTest):
    def setUp(self):
        TeledynePublicationTest.setUp(self)


