"""
@package mi.instrument.seabird.sbe54tps.ooicore.test.test_driver
@file /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe54tps/ooicore/driver.py
@author Roger Unwin
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe54tps/ooicore
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe54tps/ooicore -a UNIT
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe54tps/ooicore -a INT
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe54tps/ooicore -a QUAL
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
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

from interface.objects import AgentCommand
from mi.idk.util import convert_enum_to_dict
from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_fsm import InstrumentFSM

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.seabird.sbe54tps.ooicore.driver import InstrumentDriver
from mi.instrument.seabird.sbe54tps.ooicore.driver import ProtocolState
from mi.instrument.seabird.sbe54tps.ooicore.driver import Parameter
from mi.instrument.seabird.sbe54tps.ooicore.driver import PACKET_CONFIG
from mi.instrument.seabird.sbe54tps.ooicore.driver import ProtocolEvent
from mi.instrument.seabird.sbe54tps.ooicore.driver import Capability
from mi.instrument.seabird.sbe54tps.ooicore.driver import Prompt
from mi.instrument.seabird.sbe54tps.ooicore.driver import Protocol
from mi.instrument.seabird.sbe54tps.ooicore.driver import InstrumentCmds
from mi.instrument.seabird.sbe54tps.ooicore.driver import NEWLINE
from mi.instrument.seabird.sbe54tps.ooicore.driver import SBE54tpsStatusDataParticle, SBE54tpsStatusDataParticleKey
from mi.instrument.seabird.sbe54tps.ooicore.driver import SBE54tpsEventCounterDataParticle, SBE54tpsEventCounterDataParticleKey
from mi.instrument.seabird.sbe54tps.ooicore.driver import SBE54tpsSampleDataParticle, SBE54tpsSampleDataParticleKey
from mi.instrument.seabird.sbe54tps.ooicore.driver import SBE54tpsHardwareDataParticle, SBE54tpsHardwareDataParticleKey
from mi.instrument.seabird.sbe54tps.ooicore.driver import SBE54tpsConfigurationDataParticle, SBE54tpsConfigurationDataParticleKey


from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from prototype.sci_data.stream_defs import ctd_stream_definition

# SAMPLE DATA FOR TESTING
from mi.instrument.seabird.sbe54tps.ooicore.test.sample_data import *
from mi.instrument.seabird.sbe54tps.ooicore.test.params import PARAMS

from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

from mi.core.exceptions import SampleException, InstrumentParameterException, InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException, InstrumentCommandException
from mi.core.instrument.instrument_driver import DriverParameter, DriverConnectionState, DriverAsyncEvent
from mi.core.instrument.chunker import StringChunker

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe54tps.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = PACKET_CONFIG,
    instrument_agent_stream_definition = ctd_stream_definition(stream_id=None),

    driver_startup_config = {
        Parameter.SAMPLE_PERIOD: 15,
        Parameter.BATTERY_TYPE: 1,
        Parameter.UPLOAD_TYPE: 1,
        Parameter.ENABLE_ALERTS: 1,
        #Parameter.TIME: current time.... not sure how.
    }
)


# Globals
raw_stream_received = False
parsed_stream_received = False

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


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)
	###
	# 	Reset test verification variables.  The purpose of this method is
	#	to reset the test verification variables to initial values.  The
	#	individual tests should cause the variables to be set (for instance,
	#	raw_stream_received would be set to True), and the tests should verify
	#	that the variables have been set to the expected values.
	###
    def reset_test_vars(self):	
        self.raw_stream_received = False
        self.parsed_stream_received = False

	###
	#	This is the callback that would normally publish events 
	#	(streams, state transitions, etc.).
	#	Use this method to test for existence of events and to examine their
	#	attributes for correctness.
	###         	

    def my_event_callback(self, event):
        log.debug("event = " + repr(event))
        event_type = event['type']

        if event_type == DriverAsyncEvent.SAMPLE:
            sample_value = event['value']
            # the event is coming back as a string

            if 'raw' in sample_value:
                # I hate using a global, but this self is not a shared self with the test
                global raw_stream_received
                raw_stream_received = True
                log.debug("GOT A RAW")
            elif 'parsed' in sample_value:
                global parsed_stream_received
                parsed_stream_received = True
                log.debug("GOT A PARSED")
    ###
    #    Add instrument specific unit tests
    ###

    # WORKS
    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """

        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        p = Protocol(Prompt, NEWLINE, my_event_callback)
        c = Capability()

        master_list = []
        for k in convert_enum_to_dict(c):
            ret = p._filter_capabilities([getattr(c, k)])
            log.debug(str(ret))
            master_list.append(getattr(c, k))
            self.assertEqual(len(ret), 1)
        self.assertEqual(len(p._filter_capabilities(master_list)), 5)

        # Negative Testing
        self.assertEqual(len(p._filter_capabilities(['BIRD', 'ABOVE', 'WATER'])), 0)
        try:
            self.assertEqual(len(p._filter_capabilities(None)), 0)
        except TypeError:
            pass

        self.assertEqual(str(my_event_callback.mock_calls), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")

    # WORKS
    def test_prompts(self):
        """
        Verify that the prompts enumeration has no duplicate values that might cause confusion
        """
        prompts = Prompt()
        self.assert_enum_has_no_duplicates(prompts)

    # WORKS
    def test_instrument_commands_for_duplicates(self):
        """
        Verify that the InstrumentCmds enumeration has no duplicate values that might cause confusion
        """
        cmds = InstrumentCmds()
        self.assert_enum_has_no_duplicates(cmds)

    # WORKS
    def test_protocol_state_for_duplicates(self):
        """
        Verify that the ProtocolState enumeration has no duplicate values that might cause confusion
        """
        ps = ProtocolState()
        self.assert_enum_has_no_duplicates(ps)

    # WORKS
    def test_protocol_event_for_duplicates(self):
        """
        Verify that the ProtocolEvent enumeration has no duplicate values that might cause confusion
        """
        pe = ProtocolEvent()
        self.assert_enum_has_no_duplicates(pe)

    # WORKS
    def test_capability_for_duplicates(self):
        """
        Verify that the Capability enumeration has no duplicate values that might cause confusion
        """
        c = Capability()
        self.assert_enum_has_no_duplicates(c)

    # WORKS
    def test_parameter_for_duplicates(self):
        # Test ProtocolState.  Verify no Duplications.
        p = Parameter()
        self.assert_enum_has_no_duplicates(p)

    # WORKS
    def test_instrument_driver_init_(self):
        """
        @brief Test that the InstrumentDriver constructors correctly build a Driver instance.
        # should call instrument/instrument_driver SingleConnectionInstrumentDriver.__init__
        # which will call InstrumentDriver.__init__, then create a _connection_fsm and start it.
        """

        ID = InstrumentDriver(self.my_event_callback)
        self.assertEqual(ID._connection, None)
        self.assertEqual(ID._protocol, None)
        self.assertTrue(isinstance(ID._connection_fsm, InstrumentFSM))
        self.assertEqual(ID._connection_fsm.current_state, DriverConnectionState.UNCONFIGURED)

    # WORKS
    def test_instrument_driver_build_protocol(self):
        """
        mock create an instance instrument driver protocol object. Verify that it supports available commands.
        verify the handlers are present and correctly associated.
        """

        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()

        self.assertEqual(ID._protocol._newline, NEWLINE)
        self.assertEqual(ID._protocol._prompts, Prompt)
        self.assertEqual(ID._protocol._driver_event, ID._driver_event)
        self.assertEqual(ID._protocol._linebuf, '')
        self.assertEqual(ID._protocol._promptbuf, '')
        self.assertEqual(ID._protocol._datalines, [])


        for key in [
            InstrumentCmds.GET_CONFIGURATION_DATA,
            InstrumentCmds.GET_STATUS_DATA,
            InstrumentCmds.GET_EVENT_COUNTER_DATA,
            InstrumentCmds.GET_HARDWARE_DATA
        ]:
            self.assertTrue(key in ID._protocol._build_handlers.keys())

        for key in [
            InstrumentCmds.GET_CONFIGURATION_DATA,
            InstrumentCmds.GET_STATUS_DATA,
            InstrumentCmds.GET_EVENT_COUNTER_DATA,
            InstrumentCmds.GET_HARDWARE_DATA
        ]:
            self.assertTrue(key in ID._protocol._response_handlers.keys())

        self.assertEqual(ID._protocol._last_data_receive_timestamp, None)
        self.assertEqual(ID._protocol._connection, None)

        p = Parameter()

        for labels_value in ID._protocol._param_dict._param_dict.keys():
            log.debug("Verifying " + labels_value + " is present")
            match = False
            for i in [v for v in dir(p) if not callable(getattr(p,v))]:
                key = getattr(p, i)
                if key == labels_value:
                    match = True
            self.assertTrue(match)

        self.assertEqual(ID._protocol._protocol_fsm.enter_event, 'DRIVER_EVENT_ENTER')
        self.assertEqual(ID._protocol._protocol_fsm.exit_event, 'DRIVER_EVENT_EXIT')
        self.assertEqual(ID._protocol._protocol_fsm.previous_state, None)
        self.assertEqual(ID._protocol._protocol_fsm.current_state, 'DRIVER_STATE_UNKNOWN')
        self.assertEqual(repr(ID._protocol._protocol_fsm.states), repr(ProtocolState))
        self.assertEqual(repr(ID._protocol._protocol_fsm.events), repr(ProtocolEvent))


        state_handlers = {
            (ProtocolState.UNKNOWN, ProtocolEvent.ENTER): '_handler_unknown_enter',
            (ProtocolState.UNKNOWN, ProtocolEvent.EXIT): '_handler_unknown_exit',
            (ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER): '_handler_unknown_discover',
            (ProtocolState.UNKNOWN, ProtocolEvent.FORCE_STATE): '_handler_unknown_force_state',
            (ProtocolState.COMMAND, ProtocolEvent.FORCE_STATE): '_handler_unknown_force_state',
            (ProtocolState.COMMAND, ProtocolEvent.ENTER): '_handler_command_enter',
            (ProtocolState.COMMAND, ProtocolEvent.EXIT): '_handler_command_exit',
            (ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE): '_handler_command_start_autosample',
            (ProtocolState.COMMAND, ProtocolEvent.GET): '_handler_command_get',
            (ProtocolState.COMMAND, ProtocolEvent.SET): '_handler_command_set',
            (ProtocolState.COMMAND, ProtocolEvent.INIT_LOGGING): '_handler_command_init_logging',
            (ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC): '_handler_command_clock_sync',
            (ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS): '_handler_command_aquire_status',
            (ProtocolState.COMMAND, ProtocolEvent.START_DIRECT): '_handler_command_start_direct',
            (ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER): '_handler_autosample_enter',
            (ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT): '_handler_autosample_exit',
            (ProtocolState.AUTOSAMPLE, ProtocolEvent.GET): '_handler_command_get',
            (ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE): '_handler_autosample_stop_autosample',
            (ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER): '_handler_direct_access_enter',
            (ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT): '_handler_direct_access_exit',
            (ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT): '_handler_direct_access_execute_direct',
            (ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT): '_handler_direct_access_stop_direct'
        }



        for key in ID._protocol._protocol_fsm.state_handlers.keys():
            self.assertEqual(ID._protocol._protocol_fsm.state_handlers[key].__func__.func_name,  state_handlers[key])
            self.assertTrue(key in state_handlers)

        for key in state_handlers.keys():
            self.assertEqual(ID._protocol._protocol_fsm.state_handlers[key].__func__.func_name,  state_handlers[key])
            self.assertTrue(key in ID._protocol._protocol_fsm.state_handlers)

    # WORKS
    def test_protocol(self):
        """
        Create a mock instance of Protocol.  Assert that state handlers in the FSM and handlers are created correctly.
        """

        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        p = Protocol(Prompt, NEWLINE, my_event_callback)
        self.assertEqual(str(my_event_callback.mock_calls), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")

        p._protocol_fsm

        self.assertEqual(p._protocol_fsm.enter_event, 'DRIVER_EVENT_ENTER')
        self.assertEqual(p._protocol_fsm.exit_event, 'DRIVER_EVENT_EXIT')
        self.assertEqual(p._protocol_fsm.previous_state, None)
        self.assertEqual(p._protocol_fsm.current_state, 'DRIVER_STATE_UNKNOWN')
        self.assertEqual(repr(p._protocol_fsm.states), repr(ProtocolState))
        self.assertEqual(repr(p._protocol_fsm.events), repr(ProtocolEvent))

        state_handlers = {
            (ProtocolState.UNKNOWN, ProtocolEvent.ENTER): '_handler_unknown_enter',
            (ProtocolState.UNKNOWN, ProtocolEvent.EXIT): '_handler_unknown_exit',
            (ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER): '_handler_unknown_discover',
            (ProtocolState.UNKNOWN, ProtocolEvent.FORCE_STATE): '_handler_unknown_force_state',
            (ProtocolState.COMMAND, ProtocolEvent.FORCE_STATE): '_handler_unknown_force_state',
            (ProtocolState.COMMAND, ProtocolEvent.ENTER): '_handler_command_enter',
            (ProtocolState.COMMAND, ProtocolEvent.EXIT): '_handler_command_exit',
            (ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE): '_handler_command_start_autosample',
            (ProtocolState.COMMAND, ProtocolEvent.GET): '_handler_command_get',
            (ProtocolState.COMMAND, ProtocolEvent.SET): '_handler_command_set',
            (ProtocolState.COMMAND, ProtocolEvent.INIT_LOGGING): '_handler_command_init_logging',
            (ProtocolState.COMMAND, ProtocolEvent.CLOCK_SYNC): '_handler_command_clock_sync',
            (ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_STATUS): '_handler_command_aquire_status',
            (ProtocolState.COMMAND, ProtocolEvent.START_DIRECT): '_handler_command_start_direct',
            (ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER): '_handler_autosample_enter',
            (ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT): '_handler_autosample_exit',
            (ProtocolState.AUTOSAMPLE, ProtocolEvent.GET): '_handler_command_get',
            (ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE): '_handler_autosample_stop_autosample',
            (ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER): '_handler_direct_access_enter',
            (ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT): '_handler_direct_access_exit',
            (ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT): '_handler_direct_access_execute_direct',
            (ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT): '_handler_direct_access_stop_direct'
        }







        log.debug(str(state_handlers[(ProtocolState.UNKNOWN, ProtocolEvent.EXIT)]))
        for key in p._protocol_fsm.state_handlers.keys():
            #log.debug("W*****>>> " + str(key))
            #log.debug("X*****>>> " + str(p._protocol_fsm.state_handlers[key].__func__.func_name))
            #log.debug("Y*****>>> " + str(state_handlers[key]))
            self.assertEqual(p._protocol_fsm.state_handlers[key].__func__.func_name,  state_handlers[key])
            self.assertTrue(key in state_handlers)

        for key in state_handlers.keys():
            self.assertEqual(p._protocol_fsm.state_handlers[key].__func__.func_name,  state_handlers[key])
            self.assertTrue(key in p._protocol_fsm.state_handlers)

    # WORKS
    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """

        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        p = Protocol(Prompt, NEWLINE, my_event_callback)
        c = Capability()

        master_list = []
        for k in convert_enum_to_dict(c):
            ret = p._filter_capabilities([getattr(c, k)])
            log.debug(str(ret))
            master_list.append(getattr(c, k))
            self.assertEqual(len(ret), 1)
        self.assertEqual(len(p._filter_capabilities(master_list)), 5)

        # Negative Testing
        self.assertEqual(len(p._filter_capabilities(['BIRD', 'ABOVE', 'WATER'])), 0)
        try:
            self.assertEqual(len(p._filter_capabilities(None)), 0)
        except TypeError:
            pass

        self.assertEqual(str(my_event_callback.mock_calls), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")

    # WORKS
    def test_protocol_handler_unknown_enter(self):
        """
        mock call _handler_unknown_enter and verify that it performs teh correct sub-calls
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        p = Protocol(Prompt, NEWLINE, my_event_callback)

        args = []
        kwargs =  {}
        p._handler_unknown_enter(*args, **kwargs)
        self.assertEqual(str(my_event_callback.call_args_list), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE'),\n call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")

    # WORKS
    def test_protocol_handler_unknown_exit(self):
        """
        mock call _handler_unknown_exit and verify that it performs teh correct sub-calls
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        p = Protocol(Prompt, NEWLINE, my_event_callback)

        args = []
        kwargs =  {}
        p._handler_unknown_exit(*args, **kwargs)
        self.assertEqual(str(my_event_callback.call_args_list), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")


    @unittest.skip('Need to write unknown_discover')
    def test_protocol_handler_unknown_discover(self):
        """
        Test 3 paths through the func ( ProtocolState.UNKNOWN, ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE)
            For each test 3 paths of Parameter.LOGGING = ( True, False, Other )
        """


        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol
        #
        # current_state = ProtocolState.UNKNOWN
        #

        ID._protocol._protocol_fsm.current_state = ProtocolState.UNKNOWN

        args = []
        kwargs = ({'timeout': 30,})

        do_cmd_resp_mock = Mock(spec="do_cmd_resp_mock")
        p._do_cmd_resp = do_cmd_resp_mock
        _wakeup_mock = Mock(spec="wakeup_mock")
        p._wakeup = _wakeup_mock


        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[]")
        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_AUTOSAMPLE')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_STREAMING')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[call(delay=0.5, timeout=30), call(30)]')

        self.assertEqual("[call('ds', timeout=30), call('dc', timeout=30)]", str(do_cmd_resp_mock.mock_calls))

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_COMMAND')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_IDLE')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[call(delay=0.5, timeout=30), call(30)]')
        self.assertTrue("[call('ds', timeout=30), call('dc', timeout=30)]" in str(do_cmd_resp_mock.mock_calls))

        #
        # current_state = ProtocolState.COMMAND
        #

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        p._protocol_fsm.current_state = ProtocolState.COMMAND

        args = []
        kwargs =  dict({'timeout': 30,})

        do_cmd_resp_mock = Mock(spec="do_cmd_resp_mock")
        p._do_cmd_resp = do_cmd_resp_mock
        _wakeup_mock = Mock(spec="wakeup_mock")
        p._wakeup = _wakeup_mock

        v = Mock(spec="val")
        v.value = None
        p._param_dict.set(Parameter.LOGGING, v)
        ex_caught = False
        try:
            (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        except InstrumentStateException:
            ex_caught = True
        self.assertTrue(ex_caught)
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")
        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v = Mock(spec="val")

        v.value = True
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_AUTOSAMPLE')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_STREAMING')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v.value = False
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_COMMAND')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_IDLE')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")

        #
        # current_state = ProtocolState.AUTOSAMPLE
        #

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        p._protocol_fsm.current_state = ProtocolState.COMMAND

        args = []
        kwargs =  dict({'timeout': 30,})

        do_cmd_resp_mock = Mock(spec="do_cmd_resp_mock")
        p._do_cmd_resp = do_cmd_resp_mock
        _wakeup_mock = Mock(spec="wakeup_mock")
        p._wakeup = _wakeup_mock

        v = Mock(spec="val")
        v.value = None
        p._param_dict.set(Parameter.LOGGING, v)
        ex_caught = False
        try:
            (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        except InstrumentStateException:
            ex_caught = True
        self.assertTrue(ex_caught)
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")
        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v = Mock(spec="val")

        v.value = True
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_AUTOSAMPLE')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_STREAMING')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v.value = False
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_COMMAND')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_IDLE')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")

    # WORKS
    def test_protocol_unknown_force_state(self):
        """
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol

        args = []
        kwargs =  dict({'timeout': 30,})
        ex_caught = False
        try:
            (next_state, result) = p._handler_unknown_force_state(*args, **kwargs)
        except InstrumentParameterException:
            ex_caught = True
        self.assertTrue(ex_caught)

        kwargs = dict({'timeout': 30,
                       'state': 'ARDVARK'})

        (next_state, result) = p._handler_unknown_force_state(*args, **kwargs)
        self.assertEqual(next_state, 'ARDVARK')
        self.assertEqual(result, 'ARDVARK')

    # WORKS
    def test_protocol_handler_command_enter(self):
        """
        mock call _handler_command_enter and verify that it performs teh correct sub-calls
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol
        _update_params_mock = Mock(spec="update_params")
        p._update_params = _update_params_mock

        _update_driver_event = Mock(spec="driver_event")
        p._driver_event = _update_driver_event
        args = []
        kwargs =  dict({'timeout': 30,})

        ret = p._handler_command_enter(*args, **kwargs)
        self.assertEqual(ret, None)
        self.assertEqual(str(_update_params_mock.mock_calls), "[call()]")
        self.assertEqual(str(_update_driver_event.mock_calls), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")


    @unittest.skip('Need to write unknown_discover')
    def parse_getcd_response(self):
        """
        @return:
        """

    @unittest.skip('Need to write unknown_discover')
    def parse_getsd_response(self):
        """
        @return:
        """

    @unittest.skip('Need to write unknown_discover')
    def parse_getec_response(self):
        """
        @return:
        """

    @unittest.skip('Need to write unknown_discover')
    def parse_gethd_response(self):
        """
        @return:
        """

    # WORKS
    def test_build_set_command(self):
        """
        verify the build set command performs correctly
        should return setvar=value\r\n
        test for float, string, date, Boolean
        PU0 FLOAT 5.827424
        SHOW_PROGRESS_MESSAGES True Boolean
        self.assertEqual(str(p._param_dict.get('TCALDATE')),'(30, 3, 2012)')
        USER_INFO OOI str,
        TIDE_INTERVAL


        Int BATTERY_TYPE = "BatteryType"        # SetBatteryType
        Int BAUD_RATE = "BaudRate"              # SetBaudRate
        TIME = "Time"                       # SetTime
        Bool ENABLE_ALERTS = "EnableAlerts"      # SetEnableAlerts
        Int UPLOAD_TYPE = "UploadType"          # SetUploadType
        Int SAMPLE_PERIOD = "SamplePeriod"      # SetSamplePeriod
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol


        # Int
        ret = p._build_set_command("irrelevant", Parameter.SAMPLE_PERIOD, 200)
        self.assertEqual(ret, 'SETsampleperiod=200\r\n')

        # Float
        # ret = p._build_set_command("irrelevant", Parameter.MIN_ALLOWABLE_ATTENUATION, 5.827424)
        # self.assertEqual(ret, 'MIN_ALLOWABLE_ATTENUATION=5.827424\r\n')

        # Boolean - 1/0
        ret = p._build_set_command("irrelevant", Parameter.ENABLE_ALERTS, True)
        self.assertEqual(ret, 'SETenablealerts=1\r\n')

        # String
        # ret = p._build_set_command("irrelevant", Parameter.USER_INFO, 'ooi_test')
        # self.assertEqual(ret, 'USERINFO=ooi_test\r\n')

        # Not used now DC set power removed.
        # Date (Tuple)
        # ret = p._build_set_command("irrelevant", Parameter.TCALDATE, (30, 8, 2012))
        # self.assertEqual(ret, 'TCALDATE=30-Aug-12\r\n')

    # WORKS
    def test_handler_command_set(self):
        """
        Verify that we can set parameters
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol


        attrs = {'return_value': '_do_cmd_resp was returned'}
        _do_cmd_resp_mock = Mock(**attrs)
        _update_params_mock = Mock()

        p._do_cmd_resp = _do_cmd_resp_mock
        p._update_params = _update_params_mock

        params = {
            Parameter.SAMPLE_PERIOD : 400,
            #DC#Parameter.PD1 : int(1),
            #DC#Parameter.PD2 : True,
        }
        args = params
        kwargs = {}

        (next_state, result) = p._handler_command_set(args, **kwargs)
        self.assertEqual(str(_do_cmd_resp_mock.mock_calls),"[call('set', 'sampleperiod', 400)]")
        self.assertEqual(str(_update_params_mock.mock_calls), "[call()]")
        self.assertEqual(next_state, None)
        self.assertEqual(str(result), "_do_cmd_resp was returned")

        ex_caught = False
        try:
            (next_state, result) = p._handler_command_set("WRONG", **kwargs)
        except InstrumentParameterException:
            ex_caught = True
        self.assertTrue(ex_caught)

        args = []
        ex_caught = False
        try:
            (next_state, result) = p._handler_command_set(*args, **kwargs)
        except InstrumentParameterException:
            ex_caught = True
        self.assertTrue(ex_caught)

    # WORKS
    def test_handler_command_autosample_test_get(self):
        """
        Verify that we are able to get back a variable setting correctly
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol

        # Fill the DC/DS response
        #p._parse_dc_response(SAMPLE_DC, Prompt.COMMAND)
        #p._parse_ds_response(SAMPLE_DS, Prompt.COMMAND)

        kwargs = {}
        p._handler_command_get(DriverParameter.ALL, **kwargs)

        args = [Parameter.SAMPLE_PERIOD]
        kwargs = {}
        (next_state, result) = p._handler_command_get(args, **kwargs)
        self.assertEqual(next_state, None)
        self.assertEqual(result, {'sampleperiod': None})

    # WORKS
    def test_handler_command_start_autosample(self):
        """
        verify startautosample sends the start command to the instrument.
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol
        _wakeup_mock = Mock(spec="wakeup_mock")
        p._wakeup = _wakeup_mock

        _connection_mock = Mock(spec="_connection")
        _connection_send_mock = Mock(spec="_connection_send")
        _do_cmd_resp_mock = Mock(spec="_do_cmd_resp")
        p._connection = _connection_mock
        p._connection.send = _connection_send_mock
        p._do_cmd_resp = _do_cmd_resp_mock
        args = []
        kwargs = {}
        (next_state, result) = p._handler_command_start_autosample(*args, **kwargs)
        self.assertEqual(next_state,  ProtocolState.AUTOSAMPLE)
        self.assertEqual(result, ('RESOURCE_AGENT_STATE_STREAMING', None))
        self.assertEqual(str(_connection_send_mock.mock_calls), "[call('Start\\r\\n')]")

    # WORKS
    def test_get_resource_capabilities(self):
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol
        args = []
        kwargs = {}

        # Force State UNKNOWN
        ID._protocol._protocol_fsm.current_state = ProtocolState.UNKNOWN

        ret = ID.get_resource_capabilities(*args, **kwargs)
        self.assertEqual(ret[0], [])

        # Force State COMMAND
        ID._protocol._protocol_fsm.current_state = ProtocolState.COMMAND

        ret = ID.get_resource_capabilities(*args, **kwargs)
        for state in ['DRIVER_EVENT_ACQUIRE_STATUS',
                      'DRIVER_EVENT_START_AUTOSAMPLE', 'DRIVER_EVENT_CLOCK_SYNC']:

            self.assertTrue(state in ret[0])
        self.assertEqual(len(ret[0]), 3)




        # Force State AUTOSAMPLE
        ID._protocol._protocol_fsm.current_state = ProtocolState.AUTOSAMPLE

        ret = ID.get_resource_capabilities(*args, **kwargs)
        for state in ['DRIVER_EVENT_STOP_AUTOSAMPLE']:
            self.assertTrue(state in ret[0])
        self.assertEqual(len(ret[0]), 1)

        # Force State DIRECT_ACCESS
        ID._protocol._protocol_fsm.current_state = ProtocolState.DIRECT_ACCESS

        ret = ID.get_resource_capabilities(*args, **kwargs)
        self.assertEqual(ret[0], [])

    def assert_chunker_line_by_line(self, sample):
        """
        @sample: a string containing a full record suitable for the chunker.
        pass it into the chunker char by char and verify that it finds the particle once and only once
        """

        log.debug("SAMPLE = " + repr(sample))
        self._chunker = StringChunker(Protocol.sieve_function)

        hit_count = 0
        for line in sample.split(NEWLINE):
            self._chunker.add_chunk(line + NEWLINE)

            result = self._chunker.get_next_data(clean=True)
            if result != None:
                log.debug("GOT A MATCH = " + repr(result))
                hit_count = hit_count + 1

        return hit_count == 1

    def test_chunker_line_by_line(self):
        """
        Pass all 5 output samples to the chunker
        """
        log.debug("-------------------SAMPLE_SAMPLE------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(SAMPLE_SAMPLE))
        log.debug("-------------------SAMPLE_GETHD------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(SAMPLE_GETHD))
        log.debug("-------------------SAMPLE_GETEC------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(SAMPLE_GETEC))
        log.debug("-------------------SAMPLE_GETCD------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(SAMPLE_GETCD))
        log.debug("-------------------SAMPLE_GETSD------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(SAMPLE_GETSD))

    def test_chunker_line_by_line_with_noise(self):
        """
        Pass all 5 output samples to the chunker, add in some noise
        """
        BEFORE_NOISE = "this is some before sample noise\r\nand some more\n\r"
        AFTER_NOISE = "\rThe Quick Brown Fox blah blah\nKILLROY WAS HERE\r\n"
        log.debug("-------------------SAMPLE_SAMPLE------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(BEFORE_NOISE + SAMPLE_SAMPLE + AFTER_NOISE))
        log.debug("-------------------SAMPLE_GETHD------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(BEFORE_NOISE + SAMPLE_GETHD + AFTER_NOISE))
        log.debug("-------------------SAMPLE_GETEC------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(BEFORE_NOISE + SAMPLE_GETEC + AFTER_NOISE))
        log.debug("-------------------SAMPLE_GETCD------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(BEFORE_NOISE + SAMPLE_GETCD + AFTER_NOISE))
        log.debug("-------------------SAMPLE_GETSD------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(BEFORE_NOISE + SAMPLE_GETSD + AFTER_NOISE))

    def test_chunker_line_by_line_with_bad_data(self):
        """
        Pass all 5 output samples to the chunker, screw up the samples subtlly to make them not be recognized
        """
        log.debug("-------------------SAMPLE_SAMPLE------------------------")
        self.assertFalse(self.assert_chunker_line_by_line(SAMPLE_SAMPLE.replace("<","[")))
        log.debug("-------------------SAMPLE_GETHD------------------------")
        self.assertFalse(self.assert_chunker_line_by_line(SAMPLE_GETHD.replace(">","}")))
        log.debug("-------------------SAMPLE_GETEC------------------------")
        self.assertFalse(self.assert_chunker_line_by_line(SAMPLE_GETEC.replace("<","(")))
        log.debug("-------------------SAMPLE_GETCD------------------------")
        self.assertFalse(self.assert_chunker_line_by_line(SAMPLE_GETCD.replace(">","<")))
        log.debug("-------------------SAMPLE_GETSD------------------------")
        self.assertFalse(self.assert_chunker_line_by_line(SAMPLE_GETSD.replace("=","^")))

    def assert_chunker_chr_by_chr(self, sample):
        """
        @sample: a string containing a full record suitable for the chunker.
        pass it into the chunker char by char and verify that it finds the particle once and only once
        """

        # This will want to be created in the driver eventually...
        self._chunker = StringChunker(Protocol.sieve_function)

        hit_count = 0
        for character in sample:
            self._chunker.add_chunk(character)

            result = self._chunker.get_next_data(clean=True)
            if result != None:
                hit_count = hit_count + 1

        return hit_count == 1

    def test_chunker_chr_by_chr(self):
        """
        Pass all 5 output samples to the chunker
        """
        log.debug("-------------------SAMPLE_SAMPLE------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(SAMPLE_SAMPLE))
        log.debug("-------------------SAMPLE_GETHD------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(SAMPLE_GETHD))
        log.debug("-------------------SAMPLE_GETEC------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(SAMPLE_GETEC))
        log.debug("-------------------SAMPLE_GETCD------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(SAMPLE_GETCD))
        log.debug("-------------------SAMPLE_GETSD------------------------")
        self.assertTrue(self.assert_chunker_line_by_line(SAMPLE_GETSD))

    def test_chunker_chr_by_chr_with_noise(self):
        """
        Pass all 5 output samples to the chunker, add in some noise
        """
        BEFORE_NOISE = "this is some before sample noise\r\nand some more\n\r"
        AFTER_NOISE = "\rThe Quick Brown Fox blah blah\nKILLROY WAS HERE\r\n"
        log.debug("-------------------SAMPLE_SAMPLE------------------------")
        self.assertTrue(self.assert_chunker_chr_by_chr(BEFORE_NOISE + SAMPLE_SAMPLE + AFTER_NOISE))
        log.debug("-------------------SAMPLE_GETHD------------------------")
        self.assertTrue(self.assert_chunker_chr_by_chr(BEFORE_NOISE + SAMPLE_GETHD + AFTER_NOISE))
        log.debug("-------------------SAMPLE_GETEC------------------------")
        self.assertTrue(self.assert_chunker_chr_by_chr(BEFORE_NOISE + SAMPLE_GETEC + AFTER_NOISE))
        log.debug("-------------------SAMPLE_GETCD------------------------")
        self.assertTrue(self.assert_chunker_chr_by_chr(BEFORE_NOISE + SAMPLE_GETCD + AFTER_NOISE))
        log.debug("-------------------SAMPLE_GETSD------------------------")
        self.assertTrue(self.assert_chunker_chr_by_chr(BEFORE_NOISE + SAMPLE_GETSD + AFTER_NOISE))

    def test_chunker_chr_by_chr_with_bad_data(self):
        """
        Pass all 5 output samples to the chunker, screw up the samples subtlly to make them not be recognized
        """
        log.debug("-------------------SAMPLE_SAMPLE------------------------")
        self.assertFalse(self.assert_chunker_chr_by_chr(SAMPLE_SAMPLE.replace("'","\"")))
        log.debug("-------------------SAMPLE_GETHD------------------------")
        self.assertFalse(self.assert_chunker_chr_by_chr(SAMPLE_GETHD.replace("/","!")))
        log.debug("-------------------SAMPLE_GETEC------------------------")
        self.assertFalse(self.assert_chunker_chr_by_chr(SAMPLE_GETEC.replace("/","\\")))
        log.debug("-------------------SAMPLE_GETCD------------------------")
        self.assertFalse(self.assert_chunker_chr_by_chr(SAMPLE_GETCD.replace(">","+")))
        log.debug("-------------------SAMPLE_GETSD------------------------")
        self.assertFalse(self.assert_chunker_chr_by_chr(SAMPLE_GETSD.replace("'","^")))

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    # WORKS
    def check_state(self, desired_state):
        state = self.driver_client.cmd_dvr('get_resource_state')

        # 'DRIVER_STATE_AUTOSAMPLE' != 'DRIVER_STATE_COMMAND'
        if ProtocolState.AUTOSAMPLE == state:
            # OH SNAP! WE'RE IN AUTOSAMPLE AGAIN!
            # QUICK, FIX IT BEFORE ANYONE NOTICES!

            reply = self.driver_client.cmd_dvr('execute_resource', Capability.STOP_AUTOSAMPLE)
            # NOW RE_GRAB THE STATE...
            state = self.driver_client.cmd_dvr('get_resource_state')
            #  ...AND MAKE LIKE THIS NEVER HAPPENED!
        self.assertEqual(state, desired_state)

    # WORKS
    def test_startup_configuration(self):
        '''
        Test that the startup configuration is applied correctly
        '''
        self.put_instrument_in_command_mode()

        result = self.driver_client.cmd_dvr('apply_startup_params')

        reply = self.driver_client.cmd_dvr('get_resource', [Parameter.ALL])


        self.assertEqual(reply[Parameter.SAMPLE_PERIOD], 15)
        self.assertEqual(reply[Parameter.BATTERY_TYPE], 1)
        self.assertEqual(reply[Parameter.UPLOAD_TYPE], 1)
        self.assertEqual(reply[Parameter.ENABLE_ALERTS], 1)



    # WORKS
    def put_instrument_in_command_mode(self):
        log.info("test_connect test started")

        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        log.debug("DRIVER_STARTUP_CONFIG = " + repr(self.test_config.driver_startup_config))
        reply = self.driver_client.cmd_dvr('connect', self.test_config.driver_startup_config )

        # Test the driver is in unknown state.
        self.check_state(ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        self.check_state(ProtocolState.COMMAND)

    # WORKS
    def assert_param_dict(self, pd, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """

        # Make it loop through once to warn with debugging of issues, 2nd time can send the exception
        # PARAMS is the master type list

        if all_params:
            #log.debug("DICT 1 *********" + str(pd.keys()))
            #log.debug("DICT 2 *********" + str(PARAMS.keys()))
            self.assertEqual(set(pd.keys()), set(PARAMS.keys())) # set() sorts...

            for (key, type_val) in PARAMS.iteritems():
                # EventCounter does not always populate in device output
                if key not in [
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
                    SBE54tpsEventCounterDataParticleKey.ERROR_12,
                    SBE54tpsEventCounterDataParticleKey.DEVICE_TYPE
                ]:
                    log.debug("pd[" + str(key) + "] is of type " + str(type_val) +  " ?= " + str(type(pd[key])))
                    self.assertTrue(isinstance(pd[key], type_val))
                else:
                    log.debug("pd[" + str(key) + "] MAY be None due to the param_dict not having a default parser val = " + str(pd[key]))
        else:
            for (key, val) in pd.iteritems():
                self.assertTrue(PARAMS.has_key(key))

                if val is not None: # If its not defined, lets just skip it, only catch wrong type assignments.

                    #log.debug("Asserting that " + key +  " is of type  " + str(type(val)) + " ?= " + str(PARAMS[key]))
                    self.assertTrue(isinstance(val, PARAMS[key]))
                else:
                    log.debug("*** Skipping " + repr(key) + " Because value is None ***")

    ###
    #    Add instrument specific integration tests
    ###

    # WORKS
    def test_init_logging(self):
        """
        @brief Test initialize logging command.
        """
        self.put_instrument_in_command_mode()

        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.INIT_LOGGING)

        self.assertTrue(reply)

    # WORKS
    def assert_set(self, settings_dict):
        reply = self.driver_client.cmd_dvr('set_resource', settings_dict)
        self.assertEqual(reply, None)
        reply_dict = self.driver_client.cmd_dvr('get_resource', settings_dict.keys())

        for (key, val) in settings_dict.iteritems():
            log.debug("ASSERTING " + str(key) + " WAS SET TO " + str(val) + " ACTUAL VALUE " + str(reply_dict[key]))
            self.assertEqual(reply_dict[key], settings_dict[key])

    # WORKS
    def test_get_set(self):
        """
        Test device parameter access.
        """

        self.put_instrument_in_command_mode()

        log.debug("get/set Test 1 - SAMPLE_PERIOD ")
        params = {
            Parameter.SAMPLE_PERIOD : 55,
        }
        self.assert_set(params)


        log.debug("get/set Test 2 - get master set of possible parameters using array containing Parameter.ALL")

        params3 = [
            Parameter.ALL,
        ]
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_param_dict(reply, all_params=True )

        log.debug("get/set Test 3 - set time.")

        params = {
            Parameter.TIME : "2010-10-10T10:10:10",
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)

        set_time_to = time.mktime(time.strptime("2010-10-10T10:10:10", "%Y-%m-%dT%H:%M:%S"))
        time_got_back = time.mktime(time.strptime(reply[Parameter.TIME], "%Y-%m-%dT%H:%M:%S"))
        self.assertTrue((time_got_back - set_time_to) < 15)
        self.assert_param_dict(reply)

        log.debug("get/set Test 4 - alter upload_type, enable_alerts, sample_period")
        params = {
            Parameter.UPLOAD_TYPE: 1,
            Parameter.ENABLE_ALERTS: True,
            Parameter.SAMPLE_PERIOD: 199
        }
        self.assert_set(params)

        log.debug("get/set Test 5 - get master set of possible parameters.")
        params = Parameter

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_param_dict(reply, all_params=True )


        log.debug("get/set Test 6 - Negative testing, broken values. Should get exception")
        params = {
            Parameter.ENABLE_ALERTS : 5.01,
        }
        exception = False
        try:
            log.debug("BEFORE SET_RESOURCE")
            reply = self.driver_client.cmd_dvr('set_resource', params)
            log.debug("AFTER SET_RESOURCE REPLY =" + str(reply))
        except InstrumentParameterException:
            exception = True
            log.debug("SCORE! I got an exception!")
        self.assertTrue(exception)

        log.debug("get/set Test 8 - Negative testing, broken labels. Should get exception")
        params = {
            "ROGER" : 5,
            "PETER RABBIT" : True,
            "WEB" : float(2.0),
            }
        exception = False
        try:
            reply = self.driver_client.cmd_dvr('set_resource', params)
        except InstrumentParameterException:
            exception = True
            log.debug("SCORE! I got an exception!")
        self.assertTrue(exception)

        log.debug("get/set Test 9 - Negative testing, empty params dict")
        params = {
        }

        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_param_dict(reply)

        log.debug("get/set Test 10 - Negative testing, None instead of dict")
        exception = False
        try:
            reply = self.driver_client.cmd_dvr('set_resource', None)
        except InstrumentParameterException:
            exception = True
        self.assertTrue(exception)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_param_dict(reply)

        log.debug("get/set Test N - Conductivity = Y, full set of set variables to known sane values.")
        params = {
            Parameter.TIME : time.strftime("%Y-%m-%dT%H:%M:%S"),
            Parameter.UPLOAD_TYPE: 0,
            Parameter.ENABLE_ALERTS: False,
            Parameter.SAMPLE_PERIOD: 60
            }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_param_dict(reply)

    # WORKS
    def test_get_resource_capabilities(self):
        """
        Test get resource capabilities.
        """
        # Test the driver is in state unconfigured.
        self.put_instrument_in_command_mode()

        # COMMAND
        (res_cmds, res_params) = self.driver_client.cmd_dvr('get_resource_capabilities')
        for state in ['DRIVER_EVENT_ACQUIRE_STATUS',
                      'DRIVER_EVENT_START_AUTOSAMPLE', 'DRIVER_EVENT_CLOCK_SYNC']:
            self.assertTrue(state in res_cmds)
        self.assertEqual(len(res_cmds), 3)

        # Verify all paramaters are present in res_params

        # DS
        log.debug("RES_COMMANDS = " + repr(res_params))

        for p in res_params:
            log.debug("*** ASSERTING " + str(p) + " in PARAMS")
            self.assertTrue(p in PARAMS.keys())


        reply = self.driver_client.cmd_dvr('execute_resource', Capability.START_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.AUTOSAMPLE)


        (res_cmds, res_params) = self.driver_client.cmd_dvr('get_resource_capabilities')
        for state in ['DRIVER_EVENT_STOP_AUTOSAMPLE']:
            self.assertTrue(state in res_cmds)
        self.assertEqual(len(res_cmds), 1)
        reply = self.driver_client.cmd_dvr('execute_resource', Capability.STOP_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)


        (res_cmds, res_params) = self.driver_client.cmd_dvr('get_resource_capabilities')
        for state in ['DRIVER_EVENT_ACQUIRE_STATUS',
                      'DRIVER_EVENT_START_AUTOSAMPLE', 'DRIVER_EVENT_CLOCK_SYNC']:
            self.assertTrue(state in res_cmds)
        self.assertEqual(len(res_cmds), 3)

    # WORKS
    def test_connect_configure_disconnect(self):
        """
        @ BRIEF connect and then disconnect, verify state
        """

        self.put_instrument_in_command_mode()

        reply = self.driver_client.cmd_dvr('disconnect')
        self.assertEqual(reply, None)

        self.check_state(DriverConnectionState.DISCONNECTED)

    # WORKS
    def test_bad_commands(self):
        """
        @brief test that bad commands are handled with grace and style.
        """

        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Test bad commands in UNCONFIGURED state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr('conquer_the_world')
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("1 - conquer_the_world - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)

        # Test the driver is configured for comms.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        self.check_state(DriverConnectionState.DISCONNECTED)

        # Test bad commands in DISCONNECTED state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr('test_the_waters')
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("2 - test_the_waters - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)


        # Test the driver is in unknown state.
        reply = self.driver_client.cmd_dvr('connect')
        self.check_state(ProtocolState.UNKNOWN)

        # Test bad commands in UNKNOWN state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr("skip_to_the_loo")
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("3 - skip_to_the_loo - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)



        # Test the driver is in command mode.
        reply = self.driver_client.cmd_dvr('discover_state')


        # probably snuck back into autosample
        self.check_state(ProtocolState.COMMAND)


        # Test bad commands in COMMAND state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr("... --- ..., ... --- ...")
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("4 - ... --- ..., ... --- ... - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)

    # WORKS
    def test_connect(self):
        """
        Test configuring and connecting to the device through the port
        agent. Discover device state.
        """
        log.info("test_connect test started")
        self.put_instrument_in_command_mode()

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')

        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

    def test_clock_sync(self):
        self.put_instrument_in_command_mode()
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.CLOCK_SYNC)
        self.check_state(ProtocolState.COMMAND)






###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

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

    # WORKS
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
        self.assert_capabilitys_present(agent_capabilities, ['RESOURCE_AGENT_EVENT_CLEAR',
                                                             'RESOURCE_AGENT_EVENT_RESET',
                                                             'RESOURCE_AGENT_EVENT_GO_DIRECT_ACCESS',
                                                             'RESOURCE_AGENT_EVENT_GO_INACTIVE',
                                                             'RESOURCE_AGENT_EVENT_PAUSE'])
        self.assert_capabilitys_present(driver_capabilities, ['DRIVER_EVENT_ACQUIRE_STATUS',
                                                              'DRIVER_EVENT_START_AUTOSAMPLE',
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

    # WORKS
    def test_connect_disconnect(self):

        self.assert_enter_command_mode()

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)

        self.check_agent_state(ResourceAgentState.UNINITIALIZED)

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
