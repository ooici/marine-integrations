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
import gevent
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

from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import WorkhorseInstrumentDriver

from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import DataParticleType
from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import WorkhorseProtocolState
from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import WorkhorseProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import WorkhorseParameter
from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import WorkhorseProtocol
from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import WorkhorseInstrumentCmds
from mi.instrument.teledyne.driver import TeledyneScheduledJob
from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import TeledynePrompt
from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import NEWLINE

from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import ADCP_SYSTEM_CONFIGURATION_KEY
from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import ADCP_SYSTEM_CONFIGURATION_DataParticle
from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import ADCP_COMPASS_CALIBRATION_KEY
from mi.instrument.teledyne.workhorse_monitor_150_khz.driver import ADCP_COMPASS_CALIBRATION_DataParticle

#from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import SAMPLE_RAW_DATA 
#from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import CALIBRATION_RAW_DATA
#from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import PS0_RAW_DATA
#from mi.instrument.teledyne.workhorse_monitor_150_khz.test.test_data import PS3_RAW_DATA
#from mi.instrument.teledyne.workhorse_monitor_150_khz.test.test_data import FD_RAW_DATA
#from mi.instrument.teledyne.workhorse_monitor_150_khz.test.test_data import PT200_RAW_DATA

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

#from mi.instrument.teledyne.test.test_driver import TeledyneParameterAltValue
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
#class WorkhorseParameterAltValue(TeledyneParameterAltValue):
    # Values that are valid, but not the ones we want to use,
    # used for testing to verify that we are setting good values.
    #

    # Probably best NOT to tweek this one.

#    SERIAL_FLOW_CONTROL = '11110'
#    BANNER = 1
#    SLEEP_ENABLE = 1
#    SAVE_NVRAM_TO_RECORDER = True # Immutable.
#    POLLED_MODE = True
#    HEADING_ALIGNMENT = 1
#    TIME_PER_BURST = '00:55:00'
#    ENSEMBLES_PER_BURST = 999
#    BUFFER_OUTPUT_PERIOD = '00:55:00'

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

    ###
    #    Add instrument specific integration tests
    ###
    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        log.error("IN test_parameters")
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        log.debug("REPLY = " + str(reply))
        self.assert_driver_parameters(reply, True)

    def test_commands(self):
        """
        Run instrument commands from both command and streaming mode.
        """
        log.error("IN test_commands")
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
        self.assert_driver_command(ProtocolEvent.SEND_LAST_SAMPLE, regex='^\x7f\x7f.*')
        self.assert_driver_command(ProtocolEvent.SAVE_SETUP_TO_RAM, expected="Parameters saved as USER defaults")
        self.assert_driver_command(ProtocolEvent.GET_ERROR_STATUS_WORD, regex='^........')
        self.assert_driver_command(ProtocolEvent.CLEAR_ERROR_STATUS_WORD, regex='^Error Status Word Cleared')
        self.assert_driver_command(ProtocolEvent.GET_FAULT_LOG, regex='^Total Unique Faults   =.*')
        self.assert_driver_command(ProtocolEvent.CLEAR_FAULT_LOG, expected='FC ..........\r\n Fault Log Cleared.\r\nClearing buffer @0x00801000\r\nDone [i=2048].\r\n')
        self.assert_driver_command(ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, regex='^Beam Width:')
        self.assert_driver_command(ProtocolEvent.RUN_TEST_200, regex='^  Ambient  Temperature =')

        ####
        # Then test in streaming mode
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

    def _test_set_serial_flow_control_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SERIAL_FLOW_CONTROL ======")

        # Test read only raise exceptions on set.
        self.assert_set_exception(WorkhorseParameter.SERIAL_FLOW_CONTROL, '10110')
        self._tested[WorkhorseParameter.SERIAL_FLOW_CONTROL] = True

    def _test_set_save_nvram_to_recorder(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SAVE_NVRAM_TO_RECORDER ======")
        self.assert_set(WorkhorseParameter.SAVE_NVRAM_TO_RECORDER, True)
        self.assert_set(WorkhorseParameter.SAVE_NVRAM_TO_RECORDER, False)

        # Test read only raise exceptions on set.
        self.assert_set(WorkhorseParameter.SAVE_NVRAM_TO_RECORDER, self._driver_parameters[WorkhorseParameter.SAVE_NVRAM_TO_RECORDER][self.VALUE])
        self._tested[WorkhorseParameter.SAVE_NVRAM_TO_RECORDER] = True

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

    def _test_set_banner(self):
        ###
        #   test get set of a variety of parameter ranges
        ###

        log.debug("====== Testing ranges for BANNER ======")

        # Test read only raise exceptions on set.
        self.assert_set(WorkhorseParameter.BANNER, True)
        self.assert_set(WorkhorseParameter.BANNER, False)

        self._tested[WorkhorseParameter.BANNER] = True
        self.assert_set(WorkhorseParameter.ENSEMBLES_PER_BURST, self._driver_parameters[WorkhorseParameter.ENSEMBLES_PER_BURST][self.VALUE])

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

    def _test_set_time_per_burst(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for TIME_PER_BURST ======")
 
        # POLLED_MODE:  -- (True/False)
        self.assert_set(WorkhorseParameter.TIME_PER_BURST, "00:00:00.00")
        self.assert_set(WorkhorseParameter.TIME_PER_BURST, "00:00:01.00")
        self.assert_set(WorkhorseParameter.TIME_PER_BURST, "00:01:00.00")
        self.assert_set(WorkhorseParameter.TIME_PER_BURST, "01:00:00.00")

        self.assert_set_exception(WorkhorseParameter.TIME_PER_BURST, "99:99:99.00")
        self.assert_set_exception(WorkhorseParameter.TIME_PER_BURST, 0)
        self.assert_set_exception(WorkhorseParameter.TIME_PER_BURST, 1399)

        self.assert_set_exception(WorkhorseParameter.TIME_PER_BURST, 1601)
        self.assert_set_exception(WorkhorseParameter.TIME_PER_BURST, "LEROY JENKINS")
        self.assert_set_exception(WorkhorseParameter.TIME_PER_BURST, -256)
        self.assert_set_exception(WorkhorseParameter.TIME_PER_BURST, -1)
        self.assert_set_exception(WorkhorseParameter.TIME_PER_BURST, 3.1415926)
        #
        # Reset to good value.
        #
        self.assert_set(WorkhorseParameter.TIME_PER_BURST, self._driver_parameters[WorkhorseParameter.TIME_PER_BURST][self.VALUE])
        self._tested[WorkhorseParameter.TIME_PER_BURST] = True

    def _test_set_ensembles_per_burst(self):
        ###
        #   test get set of a variety of parameter ranges
        # device says 0 - 65535, but it appears only to 32767 are supported.
        ###
        log.debug("====== Testing ranges for HEADING_ALIGNMENT ======")
        # HEADING_ALIGNMENT:  -- -17999 to 18000
        self.assert_set(WorkhorseParameter.ENSEMBLES_PER_BURST, 0)
        self.assert_set(WorkhorseParameter.ENSEMBLES_PER_BURST, 32767)

        self.assert_set_exception(WorkhorseParameter.ENSEMBLES_PER_BURST, -1)
        self.assert_set_exception(WorkhorseParameter.ENSEMBLES_PER_BURST, 3.1415926)
        self.assert_set_exception(WorkhorseParameter.ENSEMBLES_PER_BURST, "LEROY JENKINS")

        self.assert_set(WorkhorseParameter.ENSEMBLES_PER_BURST, self._driver_parameters[WorkhorseParameter.ENSEMBLES_PER_BURST][self.VALUE])
        self._tested[WorkhorseParameter.ENSEMBLES_PER_BURST] = True

    def _test_set_buffer_output_period(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for BUFFER_OUTPUT_PERIOD ======")
        # HEADING_ALIGNMENT:  -- -17999 to 18000
        self.assert_set(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, "00:00:00")
        self.assert_set(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, "00:05:00")
        self.assert_set(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, "05:00:00")
        self.assert_set(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, "00:00:00")
        self.assert_set(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, "23:59:59")

        self.assert_set_exception(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, 0)
        self.assert_set_exception(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, 65536)
        self.assert_set_exception(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, "99:99:99")
        self.assert_set_exception(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, -1)
        self.assert_set_exception(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, 3)
        self.assert_set_exception(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, 3.1415926)
        self.assert_set_exception(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, "LEROY JENKINS")

        self.assert_set(WorkhorseParameter.BUFFER_OUTPUT_PERIOD, self._driver_parameters[WorkhorseParameter.BUFFER_OUTPUT_PERIOD][self.VALUE])
        self._tested[WorkhorseParameter.BUFFER_OUTPUT_PERIOD] = True

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

    # need to override this because we are slow and dont feel like modifying the base class
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

    def test_direct_access_telnet_mode_command(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """

        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.SPEED_OF_SOUND, 1500)

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet()
        self.tcp_client.send_data("%sEC1488%s" % (NEWLINE, NEWLINE))
        self.tcp_client.expect(Prompt.COMMAND)
        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()
        # verify the setting got restored.
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 10)
        self.assert_get_parameter(Parameter.SPEED_OF_SOUND, 1500)

        ###
        # Test direct access inactivity timeout
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=90)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)

        ###
        # Test session timeout without activity
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=120, session_timeout=30)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)

        ###
        # Test direct access session timeout with activity
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=60)
        # Send some activity every 30 seconds to keep DA alive.
        for i in range(1, 2, 3):
            self.tcp_client.send_data(NEWLINE)
            log.debug("Sending a little keep alive communication, sleeping for 15 seconds")
            gevent.sleep(15)

        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 45)

        ###
        # Test direct access disconnect
        ###
        self.assert_direct_access_start_telnet()
        self.tcp_client.disconnect()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 30)

    def assert_resource_command_conflict_exception(self, command):
        try:
            self.assert_resource_command(command)
        except Conflict as e:
            pass
        else:
            self.assertFalse(1, "Did not raise expected Conflict exception")

    def test_commands(self):
        """
        Run instrument commands from both command and streaming mode.
        """
        log.error("IN test_commands")
        self.assert_enter_command_mode()
        ####
        # First test in command mode
        ####

        self.assert_resource_command(ProtocolEvent.START_AUTOSAMPLE)
        self.assert_resource_command(ProtocolEvent.STOP_AUTOSAMPLE)

        self.assert_resource_command(ProtocolEvent.GET_CALIBRATION)
        self.assert_resource_command(ProtocolEvent.GET_CONFIGURATION)

        self.assert_resource_command(ProtocolEvent.CLOCK_SYNC)
        self.assert_resource_command(ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_resource_command(ProtocolEvent.SEND_LAST_SAMPLE, regex='^\x7f\x7f.*')
        self.assert_resource_command(ProtocolEvent.SAVE_SETUP_TO_RAM, expected="Parameters saved as USER defaults")
        self.assert_resource_command(ProtocolEvent.GET_ERROR_STATUS_WORD, regex='^........')
        self.assert_resource_command(ProtocolEvent.CLEAR_ERROR_STATUS_WORD, regex='^Error Status Word Cleared')
        self.assert_resource_command(ProtocolEvent.GET_FAULT_LOG, regex='^Total Unique Faults   =.*')
        self.assert_resource_command(ProtocolEvent.CLEAR_FAULT_LOG, expected='FC ..........\r\n Fault Log Cleared.\r\nClearing buffer @0x00801000\r\nDone [i=2048].\r\n')
        self.assert_resource_command(ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, regex='^Beam Width:')
        self.assert_resource_command(ProtocolEvent.RUN_TEST_200, regex='^  Ambient  Temperature =')

        ####
        # Then test in streaming mode
        self.assert_resource_command(ProtocolEvent.START_AUTOSAMPLE)
        self.assert_resource_command_conflict_exception(ProtocolEvent.SEND_LAST_SAMPLE)
        self.assert_resource_command_conflict_exception(ProtocolEvent.SAVE_SETUP_TO_RAM)
        self.assert_resource_command_conflict_exception(ProtocolEvent.GET_ERROR_STATUS_WORD)
        self.assert_resource_command_conflict_exception(ProtocolEvent.CLEAR_ERROR_STATUS_WORD)
        self.assert_resource_command_conflict_exception(ProtocolEvent.GET_FAULT_LOG)
        self.assert_resource_command_conflict_exception(ProtocolEvent.CLEAR_FAULT_LOG)
        self.assert_resource_command_conflict_exception(ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX)
        self.assert_resource_command_conflict_exception(ProtocolEvent.RUN_TEST_200)
        self.assert_resource_command(ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_resource_command_conflict_exception(ProtocolEvent.CLOCK_SYNC)
        self.assert_resource_command(ProtocolEvent.GET_CALIBRATION, regex=r'ACTIVE FLUXGATE CALIBRATION MATRICES')
        self.assert_resource_command(ProtocolEvent.GET_CONFIGURATION, regex=r'HEADING  TILT 1  TILT 2')

        self.assert_resource_command(ProtocolEvent.STOP_AUTOSAMPLE)

        self.assert_resource_command_conflict_exception('ima_bad_command')
 
    def test_direct_access_telnet_autosample(self):
        """
        Verify we can handle an instrument state change while in DA
        """
        self.assert_enter_command_mode()

        # go into direct access, and muck up a setting.
        self.assert_set_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:05.00', True)
        self.assert_set_parameter(Parameter.TIME_PER_PING, '00:03.00', True)
        self.assert_set_parameter(Parameter.PINGS_PER_ENSEMBLE, 1, True)

        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data("%s%s" % (WorkhorseInstrumentCmds.START_LOGGING, NEWLINE))

        gevent.sleep(3)
        self.assert_sample_async(self.assert_particle_pd0_data, DataParticleType.ADCP_PD0_PARSED_EARTH, 20)

        self.tcp_client.disconnect()

        self.assert_state_change(ResourceAgentState.STREAMING, ProtocolState.AUTOSAMPLE, 70)

    def test_direct_access_telnet_mode_autosample(self):
        """
        @brief Same as the previous DA test except in this test
               we force the instrument into streaming when in
               DA.  Then we need to verify the transition back
               to the driver works as expected.
        """
        ###
        # First test direct access and exit with a go command
        # call.  Also add a parameter change to verify DA
        # parameters are restored on DA exit.
        ###
        self.assert_enter_command_mode()

        self.assert_set_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:05.00', True)
        self.assert_set_parameter(Parameter.TIME_PER_PING, '00:03.00', True)
        self.assert_set_parameter(Parameter.PINGS_PER_ENSEMBLE, 1, True)
        self.assert_set_parameter(Parameter.SPEED_OF_SOUND, 1500)

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data("EC1488%s" % (NEWLINE))
        self.tcp_client.expect(Prompt.COMMAND)

        self.tcp_client.send_data("%s%s" % (WorkhorseInstrumentCmds.START_LOGGING, NEWLINE))
        gevent.sleep(3)
        self.assert_sample_async(self.assert_particle_pd0_data, DataParticleType.ADCP_PD0_PARSED_EARTH, 20)
        
        self.assert_direct_access_stop_telnet() # does this work?
        #self.tcp_client.disconnect() # this one works
        
        # verify the setting got restored.
        log.error("ROGER 1---------------------------------------------")
        self.assert_state_change(ResourceAgentState.STREAMING, ProtocolState.AUTOSAMPLE, 200)
        log.error("ROGER 2---------------------------------------------")
        self.assert_get_parameter(Parameter.SPEED_OF_SOUND, 1500)
        log.error("ROGER 3---------------------------------------------")

        ###
        # Test direct access inactivity timeout
        #
        # We have to call start now after the assert because the assert
        # puts the instrument in command mode first.  you can not start DA from
        # autosample.
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=90)
        self.tcp_client.send_data("%scs%s" % (NEWLINE, NEWLINE))
        gevent.sleep(3)
        self.assert_state_change(ResourceAgentState.STREAMING, ProtocolState.AUTOSAMPLE, 200)

        ###
        # Test session timeout without activity
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=120, session_timeout=30)
        self.tcp_client.send_data("%scs%s" % (NEWLINE, NEWLINE))
        gevent.sleep(3)
        self.assert_state_change(ResourceAgentState.STREAMING, ProtocolState.AUTOSAMPLE, 60)

        ###
        # Test direct access session timeout with activity
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=60)
        self.tcp_client.send_data("%scs%s" % (NEWLINE, NEWLINE))
        # Send some activity every 30 seconds to keep DA alive.
        for i in range(1, 2, 3):
            self.tcp_client.send_data(NEWLINE)
            log.debug("Sending a little keep alive communication, sleeping for 15 seconds")
            gevent.sleep(15)

        self.assert_state_change(ResourceAgentState.STREAMING, ProtocolState.AUTOSAMPLE, 45)

    def test_direct_access_telnet_mode_autosample_disconnect(self):
        """
        @brief Same as the previous DA test except in this test
               we force the instrument into streaming when in
               DA.  Then we need to verify the transition back
               to the driver works as expected.
        """
        ###
        # First test direct access and exit with a go command
        # call.  Also add a parameter change to verify DA
        # parameters are restored on DA exit.
        ###
        self.assert_enter_command_mode()   
        ###
        # Test direct access disconnect
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=600, session_timeout=600)
        log.debug("DA server started and connected")
        self.tcp_client.send_data("%s%s" % (WorkhorseInstrumentCmds.START_LOGGING, NEWLINE))
        gevent.sleep(3)
        log.debug("DA server autosample started")
        self.tcp_client.disconnect()
        log.debug("DA server tcp client disconnected")
        gevent.sleep(60)
        self.assert_state_change(ResourceAgentState.STREAMING, ProtocolState.AUTOSAMPLE, 400)

    def test_execute_clock_sync(self):
        """
        Verify we can syncronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)

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
                ProtocolEvent.CLOCK_SYNC,
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.CLEAR_ERROR_STATUS_WORD,
                ProtocolEvent.CLEAR_FAULT_LOG,
                ProtocolEvent.GET_CALIBRATION,
                ProtocolEvent.GET_CONFIGURATION,
                ProtocolEvent.GET_ERROR_STATUS_WORD,
                ProtocolEvent.GET_FAULT_LOG,
                ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX,
                ProtocolEvent.POWER_DOWN,
                ProtocolEvent.RESTORE_FACTORY_PARAMS,
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

        params = {}
        for k in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[k]:
                if False == self._driver_parameters[k][self.READONLY]:
                    self.assert_get_parameter(k, self._driver_parameters[k][self.VALUE])
                    log.error("VERIFYING %s is set to %s appropriately ", k, str(self._driver_parameters[k][self.VALUE]))

        for k in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[k]:
                if False == self._driver_parameters[k][self.READONLY]:
                    self.assert_set_parameter(k, self._driver_parameters[k][self.OFF_VALUE])
                    log.error("VERIFYING %s is set to %s appropriately ", k, str(self._driver_parameters[k][self.OFF_VALUE]))

    def test_startup_params_second_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()
        params = {}
        for k in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[k]:
                if False == self._driver_parameters[k][self.READONLY]:
                    self.assert_get_parameter(k, self._driver_parameters[k][self.VALUE])
                    log.error("VERIFYING %s was set to %s appropriately ", k, str(self._driver_parameters[k][self.VALUE]))

        for k in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[k]:
                if False == self._driver_parameters[k][self.READONLY]:
                    self.assert_set_parameter(k, self._driver_parameters[k][self.OFF_VALUE])
                    log.error("SETTING %s to OFF_VALUE of %s ", k, str(self._driver_parameters[k][self.OFF_VALUE]))


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
