"""
@package mi.instrument.seabird.sbe26plus.test.test_driver
@file /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/driver.py
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
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore -a UNIT
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore -a INT
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore -a QUAL


    @TODO negative testing with bogus values to detect failures.
    @TODO would be nice to modify driver to test paramater allowable range and throw exception on out of range.

"""






__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

from gevent import monkey; monkey.patch_all()
import gevent
import time
import socket

import unittest
from mock import patch
from pyon.core.bootstrap import CFG

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

from interface.objects import AgentCommand
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.seabird.sbe26plus.driver import PACKET_CONFIG
from mi.instrument.seabird.sbe26plus.driver import DataParticle
from mi.instrument.seabird.sbe26plus.driver import InstrumentDriver
from mi.instrument.seabird.sbe26plus.driver import ProtocolState
from mi.instrument.seabird.sbe26plus.driver import Parameter
from mi.instrument.seabird.sbe26plus.driver import ProtocolEvent
from mi.instrument.seabird.sbe26plus.driver import Capability
from mi.instrument.seabird.sbe26plus.driver import Prompt
from mi.instrument.seabird.sbe26plus.driver import Protocol

from mi.instrument.seabird.sbe26plus.driver import InstrumentCmds
from mi.instrument.seabird.sbe26plus.driver import NEWLINE

from mi.core.instrument.instrument_driver import DriverConnectionState

from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException



from prototype.sci_data.stream_parser import PointSupplementStreamParser
from prototype.sci_data.constructor_apis import PointSupplementConstructor
from prototype.sci_data.stream_defs import ctd_stream_definition
from prototype.sci_data.stream_defs import SBE37_CDM_stream_definition
import numpy
from prototype.sci_data.stream_parser import PointSupplementStreamParser

from pyon.agent.agent import ResourceAgentClient
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

from pyon.core.exception import BadRequest
from pyon.core.exception import Conflict

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from mock import Mock
from mi.core.instrument.logger_client import LoggerClient
from mi.core.instrument.port_agent_client import PortAgentClient, PortAgentPacket
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict

###
#   Driver parameters for the tests
###


InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe26plus.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = '2E7GNV',
    instrument_agent_name = 'seabird_sbe26plus_ooicore',
    instrument_agent_packet_config = PACKET_CONFIG,
    instrument_agent_stream_definition = ctd_stream_definition(stream_id=None)
)

PARAMS = {
    # DS # parameters - contains all setsampling parameters
    Parameter.DEVICE_VERSION : str,
    Parameter.SERIAL_NUMBER : str,
    Parameter.DS_DEVICE_DATE_TIME : str, # long, # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python


    Parameter.USER_INFO : str,
    Parameter.QUARTZ_PREASURE_SENSOR_SERIAL_NUMBER : float,
    Parameter.QUARTZ_PREASURE_SENSOR_RANGE : float,

    Parameter.EXTERNAL_TEMPERATURE_SENSOR : bool,

    Parameter.CONDUCTIVITY : bool,

    Parameter.IOP_MA : float,
    Parameter.VMAIN_V : float,
    Parameter.VLITH_V : float,

    Parameter.LAST_SAMPLE_P : float,
    Parameter.LAST_SAMPLE_T : float,
    Parameter.LAST_SAMPLE_S : float,

    Parameter.TIDE_INTERVAL : int,
    Parameter.TIDE_MEASUREMENT_DURATION : int,

    Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : float,

    Parameter.WAVE_SAMPLES_PER_BURST : int,
    Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float,

    Parameter.USE_START_TIME : bool,
    #Parameter.START_TIME : str, # long, # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python
    Parameter.USE_STOP_TIME : bool,
    #Parameter.STOP_TIME : str, # long, # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python

    Parameter.TIDE_SAMPLES_PER_DAY : float,
    Parameter.WAVE_BURSTS_PER_DAY : float,
    Parameter.MEMORY_ENDURANCE : float,
    Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE : float,
    Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS : float,
    Parameter.TOTAL_RECORDED_WAVE_BURSTS : float,
    Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START : float,
    Parameter.WAVE_BURSTS_SINCE_LAST_START : float,
    Parameter.TXREALTIME : bool,
    Parameter.TXWAVEBURST : bool,
    Parameter.TXWAVESTATS : bool,
    Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : int,
    Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC : bool,
    Parameter.USE_MEASURED_TEMP_FOR_DENSITY_CALC : bool,
    Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PREASURE_SENSOR : float,
    Parameter.AVERAGE_SALINITY_ABOVE_PREASURE_SENSOR : float,
    Parameter.PREASURE_SENSOR_HEIGHT_FROM_BOTTOM : float,
    Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND : int,
    Parameter.MIN_ALLOWABLE_ATTENUATION : float,
    Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM : float,
    Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM : float,
    Parameter.HANNING_WINDOW_CUTOFF : float,
    Parameter.SHOW_PROGRESS_MESSAGES : bool,
    Parameter.STATUS : str,
    Parameter.LOGGING : bool,

    # DC # parameters verified to match 1:1 to DC output
    Parameter.PCALDATE : tuple,
    Parameter.PU0 : float,
    Parameter.PY1 : float,
    Parameter.PY2 : float,
    Parameter.PY3 : float,
    Parameter.PC1 : float,
    Parameter.PC2 : float,
    Parameter.PC3 : float,
    Parameter.PD1 : float,
    Parameter.PD2 : float,
    Parameter.PT1 : float,
    Parameter.PT2 : float,
    Parameter.PT3 : float,
    Parameter.PT4 : float,
    Parameter.FACTORY_M : float,
    Parameter.FACTORY_B : float,
    Parameter.POFFSET : float,
    Parameter.TCALDATE : tuple,
    Parameter.TA0 : float,
    Parameter.TA1 : float,
    Parameter.TA2 : float,
    Parameter.TA3 : float,

    Parameter.CCALDATE : tuple,
    Parameter.CG : float,
    Parameter.CH : float,
    Parameter.CI : float,
    Parameter.CJ : float,
    Parameter.CTCOR : float,
    Parameter.CPCOR : float,
    Parameter.CSLOPE : float,

    # End of DC
}
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


class my_sock():
    buf = ""
    def __init__(self, host, port):
        self.buf = ""
        self.host = host
        self.port = port
        # log.debug("OPEN SOCKET HOST = " + str(host) + " PORT = " + str(port))
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.host, self.port))
        self.s.settimeout(0.0)

    def read_a_char(self):
        c = None
        if len(self.buf) > 0:
            c = self.buf[0:1]
            self.buf = self.buf[1:]
        else:
            self.buf = self.s.recv(1024)
            log.debug("RAW READ GOT '" + str(repr(self.buf)) + "'")

        return c


    def peek_at_buffer(self):
        if len(self.buf) == 0:
            try:
                self.buf = self.s.recv(1024)
                log.debug("RAW READ GOT '" + str(repr(self.buf)) + "'")
            except:
                """
                Ignore this exception, its harmless
                """

        return self.buf

    def remove_from_buffer(self, remove):
        log.debug("BUF WAS " + str(repr(self.buf)))
        self.buf = self.buf.replace(remove, "")
        log.debug("BUF IS '" + str(repr(self.buf)) + "'")

    def get_data(self):
        data = ""
        try:
            ret = ""

            while True:
                c = self.read_a_char()
                if c == None:
                    break
                if c == '\n' or c == '':
                    ret += c
                    break
                else:
                    ret += c

            data = ret
        except AttributeError:
            log.debug("CLOSING - GOT AN ATTRIBUTE ERROR")
            self.s.close()
        except:
            data = ""

        if data:
            data = data.lower()
            log.debug("IN  [" + repr(data) + "]")
        return data

    def send_data(self, data, debug):
        try:
            log.debug("OUT [" + repr(data) + "]")
            self.s.sendall(data)
        except:
            log.debug("*** send_data FAILED [" + debug + "] had an exception sending [" + data + "]")



###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class InstrumentDriverUnitFromIDK(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    ###############################################################################
    #                                UNIT TESTS                                   #
    #         Unit tests test the method calls and parameters using Mock.         #
    # 1. Pick a single method within the class.                                   #
    # 2. Create an instance of the class                                          #
    # 3. If the method to be tested tries to call out, over-ride the offending    #
    #    method with a mock                                                       #
    # 4. Using above, try to cover all paths through the functions                #
    # 5. Negative testing if at all possible.                                     #
    ###############################################################################



    # Test enumerations. Verify no duplicates.

    def convert_enum_to_dict(self, obj):
        """
        @author Roger Unwin
        @brief  converts an enum to a dict

        """
        dic = {}
        for i in [v for v in dir(obj) if not callable(getattr(obj,v))]:
            if False == i.startswith('_'):
                dic[i] = getattr(obj, i)
        log.debug("enum dictionary = " + repr(dic))
        return dic

    def assert_enum_has_no_duplicates(self, obj):
        dic = self.convert_enum_to_dict(obj)
        occurances  = {}
        for k, v in dic.items():
            #v = tuple(v)
            occurances[v] = occurances.get(v,0) + 1

        for k in occurances:
            if occurances[k] > 1:
                log.error(str(obj) + " has ambigous duplicate values for '" + str(k) + "'")
                self.assertEqual(1, occurances[k])


    @unittest.skip('Need to figure out how this one works.')
    def test_prompts(self):
        # Test Parameter.  Verify no Duplications.
        prompts = Prompt()
        self.assert_enum_has_no_duplicates(prompts)


    def test_instrument_commands_for_duplicates(self):
        # Test InstrumentCmds.  Verify no Duplications.
        cmds = InstrumentCmds()
        self.assert_enum_has_no_duplicates(cmds)

    def test_protocol_state_for_duplicates(self):
        # Test ProtocolState.  Verify no Duplications.
        ps = ProtocolState()
        self.assert_enum_has_no_duplicates(ps)

    def test_protocol_event_for_duplicates(self):
        # Test ProtocolState.  Verify no Duplications.
        pe = ProtocolEvent()
        self.assert_enum_has_no_duplicates(pe)

    def test_capability_for_duplicates(self):
        # Test ProtocolState.  Verify no Duplications.
        c = Capability()
        self.assert_enum_has_no_duplicates(c)

    def test_parameter_for_duplicates(self):
        # Test ProtocolState.  Verify no Duplications.
        p = Parameter()
        self.assert_enum_has_no_duplicates(p)

    def my_event_callback(self, event):
        event_type = event['type']
        print str(event)
        if event_type == DriverAsyncEvent.SAMPLE:
            sample_value = event['value']
            stream_type = sample_value['stream_name']
            if stream_type == 'raw':
                self.raw_stream_received = True
            elif stream_type == 'parsed':
                self.parsed_stream_received = True

    def test_instrument_driver_init_(self):
        """
        NOT DONE
        # should call instrument/instrument_driver SingleConnectionInstrumentDriver.__init__
        # which will call InstrumentDriver.__init__, then create a _connection_fsm and start it.
        # 1. verify it created the FSM with the expected top level states.
        # 2. for each top level state, verify the commands.
        # 3. verify that the correct starting state is achieved.
        """

        ID = InstrumentDriver(self.my_event_callback)
        self.assertEqual(ID._connection, None)
        self.assertEqual(ID._protocol, None)
        self.assertTrue(isinstance(ID._connection_fsm, InstrumentFSM))
        self.assertEqual(ID._connection_fsm.current_state, DriverConnectionState.UNCONFIGURED)

    def test_instrument_driver_setSampling(self):
        """
        @TODO add in some args/kwargs to make this test better.
        """
        ID = InstrumentDriver(self.my_event_callback)
        mock_fsm = Mock(spec=InstrumentFSM)
        ID._connection_fsm = mock_fsm
        args = []
        kwargs =  {}
        ID.setsampling(args, kwargs)
        self.assertEqual(str(mock_fsm.mock_calls), "[call.on_event('DRIVER_EVENT_EXECUTE', 'PROTOCOL_EVENT_SETSAMPLING', [], {})]")

    def test_instrument_driver_settime(self):
        """
        @TODO add in some args/kwargs to make this test better.
        """
        ID = InstrumentDriver(self.my_event_callback)
        mock_fsm = Mock(spec=InstrumentFSM)
        ID._connection_fsm = mock_fsm
        args = []
        kwargs =  {}
        ID.settime(args, kwargs)
        self.assertEqual(str(mock_fsm.mock_calls), "'DRIVER_EVENT_EXECUTE', 'PROTOCOL_EVENT_SET_TIME', [], {})]")

    def test_instrument_driver_start(self):
        """
        @TODO add in some args/kwargs to make this test better.
        """
        ID = InstrumentDriver(self.my_event_callback)
        mock_fsm = Mock(spec=InstrumentFSM)
        ID._connection_fsm = mock_fsm
        args = []
        kwargs =  {}
        ID.start(args, kwargs)
        self.assertEqual(str(mock_fsm.mock_calls), "[call.on_event('DRIVER_EVENT_EXECUTE', 'DRIVER_EVENT_START_AUTOSAMPLE', [], {})]")

    def test_instrument_driver_dd(self):
        """
        @TODO add in some args/kwargs to make this test better.
        """
        ID = InstrumentDriver(self.my_event_callback)
        mock_fsm = Mock(spec=InstrumentFSM)
        ID._connection_fsm = mock_fsm
        args = []
        kwargs =  {}
        ID.dd(args, kwargs)
        self.assertEqual(str(mock_fsm.mock_calls), "[call.on_event('DRIVER_EVENT_EXECUTE', 'PROTOCOL_EVENT_UPLOAD_ASCII', [], {})]")

    def test_instrument_driver_ts(self):
        """
        @TODO add in some args/kwargs to make this test better.
        """
        ID = InstrumentDriver(self.my_event_callback)
        mock_fsm = Mock(spec=InstrumentFSM)
        ID._connection_fsm = mock_fsm
        args = []
        kwargs =  {}
        ID.ts(args, kwargs)
        self.assertEqual(str(mock_fsm.mock_calls), "[call.on_event('DRIVER_EVENT_EXECUTE', 'DRIVER_EVENT_ACQUIRE_SAMPLE', [], {})]")

    def test_instrument_driver_qs(self):
        """
        @TODO add in some args/kwargs to make this test better.
        """
        ID = InstrumentDriver(self.my_event_callback)
        mock_fsm = Mock(spec=InstrumentFSM)
        ID._connection_fsm = mock_fsm
        args = []
        kwargs =  {}
        ID.qs(args, kwargs)
        self.assertEqual(str(mock_fsm.mock_calls), "[call.on_event('DRIVER_EVENT_EXECUTE', 'PROTOCOL_EVENT_QUIT_SESSION', [], {})]")

    def test_instrument_driver_initlogging(self):
        """
        @TODO add in some args/kwargs to make this test better.
        """
        ID = InstrumentDriver(self.my_event_callback)
        mock_fsm = Mock(spec=InstrumentFSM)
        ID._connection_fsm = mock_fsm
        args = []
        kwargs =  {}
        ID.initlogging(args, kwargs)
        self.assertEqual(str(mock_fsm.mock_calls), "[call.on_event('DRIVER_EVENT_EXECUTE', 'PROTOCOL_EVENT_INIT_LOGGING', [], {})]")

    def test_instrument_driver_get_resource_params(self):
        """
        @TODO
        """
        ID = InstrumentDriver(self.my_event_callback)
        self.assertEqual(str(ID.get_resource_params()), str(Parameter.list()))


    def test_instrument_driver_build_protocol(self):
        #@TODO add tests for ID._protocol._sample_regexs

        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()

        self.assertEqual(ID._protocol._newline, NEWLINE)
        self.assertEqual(ID._protocol._prompts, Prompt)
        self.assertEqual(ID._protocol._driver_event, ID._driver_event)
        self.assertEqual(ID._protocol._linebuf, '')
        self.assertEqual(ID._protocol._promptbuf, '')
        self.assertEqual(ID._protocol._datalines, [])

        self.assertEqual(ID._protocol._build_handlers.keys(), ['qs', 'set', 'stop', 'dd', 'setsampling', 'dc', 'ts', 'start', 'settime', 'initlogging', 'ds'])
        self.assertEqual(ID._protocol._response_handlers.keys(), ['set', 'dd', 'setsampling', 'dc', 'ts', 'settime', 'initlogging', 'ds'])
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

        state_handlers = {('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_STOP_AUTOSAMPLE'): '_handler_autosample_stop_autosample',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'DRIVER_EVENT_ENTER'): '_handler_direct_access_enter',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_ENTER'): '_handler_command_enter',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_EVENT_EXIT'): '_handler_unknown_exit',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_INIT_LOGGING'): '_handler_command_init_logging',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_ACQUIRE_SAMPLE'): '_handler_command_acquire_sample',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'EXECUTE_DIRECT'): '_handler_direct_access_execute_direct',
                          ('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_EXIT'): '_handler_autosample_exit',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_QUIT_SESSION'): '_handler_command_quit_session',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'DRIVER_EVENT_STOP_DIRECT'): '_handler_direct_access_stop_direct',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'DRIVER_EVENT_EXIT'): '_handler_direct_access_exit',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_SET_TIME'): '_handler_command_set_time',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_FORCE_STATE'): '_handler_unknown_force_state',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_SET'): '_handler_command_set',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_START_DIRECT'): '_handler_command_start_direct',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_GET'): '_handler_command_autosample_test_get',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_SETSAMPLING'): '_handler_command_setsampling',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_START_AUTOSAMPLE'): '_handler_command_start_autosample',
                          ('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_GET'): '_handler_command_autosample_test_get',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_UPLOAD_ASCII'): '_handler_command_upload_ascii',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_EVENT_DISCOVER'): '_handler_unknown_discover',
                          ('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_ENTER'): '_handler_autosample_enter',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_EXIT'): '_handler_command_exit',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_EVENT_ENTER'): '_handler_unknown_enter'}

        for key in ID._protocol._protocol_fsm.state_handlers.keys():
            self.assertEqual(ID._protocol._protocol_fsm.state_handlers[key].__func__.func_name,  state_handlers[key])
            self.assertTrue(key in state_handlers)

        for key in state_handlers.keys():
            self.assertEqual(ID._protocol._protocol_fsm.state_handlers[key].__func__.func_name,  state_handlers[key])
            self.assertTrue(key in ID._protocol._protocol_fsm.state_handlers)

        self.assertEqual(ID._protocol.parsed_sample, {})
        self.assertEqual(ID._protocol.raw_sample, '')

    @unittest.skip('Need to figure out how this one works.')
    def test_data_particle(self):
        """
        """
        #@TODO need to see what a working data particle should do.

    @unittest.skip('Need to figure out how this one works.')
    def test_data_particle_build_parsed_values(self):
        """
        """
        #@TODO need to see what a working data particle should do.

    def test_protocol(self):
        """
        """
        #@TODO add tests for p._sample_regexs

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


        state_handlers = {('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_STOP_AUTOSAMPLE'): '_handler_autosample_stop_autosample',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'DRIVER_EVENT_ENTER'): '_handler_direct_access_enter',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_ENTER'): '_handler_command_enter',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_EVENT_EXIT'): '_handler_unknown_exit',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_INIT_LOGGING'): '_handler_command_init_logging',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_ACQUIRE_SAMPLE'): '_handler_command_acquire_sample',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'EXECUTE_DIRECT'): '_handler_direct_access_execute_direct',
                          ('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_EXIT'): '_handler_autosample_exit',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_QUIT_SESSION'): '_handler_command_quit_session',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'DRIVER_EVENT_STOP_DIRECT'): '_handler_direct_access_stop_direct',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'DRIVER_EVENT_EXIT'): '_handler_direct_access_exit',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_SET_TIME'): '_handler_command_set_time',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_FORCE_STATE'): '_handler_unknown_force_state',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_SET'): '_handler_command_set',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_START_DIRECT'): '_handler_command_start_direct',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_GET'): '_handler_command_autosample_test_get',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_SETSAMPLING'): '_handler_command_setsampling',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_START_AUTOSAMPLE'): '_handler_command_start_autosample',
                          ('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_GET'): '_handler_command_autosample_test_get',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_UPLOAD_ASCII'): '_handler_command_upload_ascii',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_EVENT_DISCOVER'): '_handler_unknown_discover',
                          ('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_ENTER'): '_handler_autosample_enter',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_EXIT'): '_handler_command_exit',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_EVENT_ENTER'): '_handler_unknown_enter'}

        for key in p._protocol_fsm.state_handlers.keys():
            self.assertEqual(p._protocol_fsm.state_handlers[key].__func__.func_name,  state_handlers[key])
            self.assertTrue(key in state_handlers)

        for key in state_handlers.keys():
            self.assertEqual(p._protocol_fsm.state_handlers[key].__func__.func_name,  state_handlers[key])
            self.assertTrue(key in p._protocol_fsm.state_handlers)

        self.assertEqual(p.parsed_sample, {})
        self.assertEqual(p.raw_sample, '')


    def test_protocol_filter_capabilities(self):
        """
        """

        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        p = Protocol(Prompt, NEWLINE, my_event_callback)
        c = Capability()

        master_list = []
        for k in self.convert_enum_to_dict(c):
            ret = p._filter_capabilities([getattr(c, k)])
            master_list.append(getattr(c, k))
            self.assertEqual(len(ret), 1)
        self.assertEqual(len(p._filter_capabilities(master_list)), 4)

        # Negative Testing
        self.assertEqual(len(p._filter_capabilities(['BIRD', 'ABOVE', 'WATER'])), 0)
        try:
            self.assertEqual(len(p._filter_capabilities(None)), 0)
        except TypeError:
            pass

        self.assertEqual(str(my_event_callback.mock_calls), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")

    def test_protocol_handler_unknown_enter(self):
        """
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        p = Protocol(Prompt, NEWLINE, my_event_callback)

        args = []
        kwargs =  {}
        p._handler_unknown_enter(args, kwargs)
        self.assertEqual(str(my_event_callback.call_args_list), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE'),\n call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")


    def test_protocol_handler_unknown_exit(self):
        """
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        p = Protocol(Prompt, NEWLINE, my_event_callback)

        args = []
        kwargs =  {}
        p._handler_unknown_exit(args, kwargs)
        self.assertEqual(str(my_event_callback.call_args_list), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")


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

        p._protocol_fsm.current_state = ProtocolState.UNKNOWN

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
            (next_state, result) = p._handler_unknown_discover(args, kwargs)
        except InstrumentStateException:
            ex_caught = True
        self.assertTrue(ex_caught)
        self.assertEqual(str(_wakeup_mock.mock_calls), '[call(delay=0.1, timeout=40), call(40)]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=40)]")
        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()



        v.value = True
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(args, kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_AUTOSAMPLE')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_STREAMING')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[call(delay=0.1, timeout=40), call(40)]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=40)]")

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v.value = False
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(args, kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_COMMAND')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_IDLE')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[call(delay=0.1, timeout=40), call(40)]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=40)]")

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
            (next_state, result) = p._handler_unknown_discover(args, kwargs)
        except InstrumentStateException:
            ex_caught = True
        self.assertTrue(ex_caught)
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=40)]")
        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v = Mock(spec="val")

        v.value = True
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(args, kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_AUTOSAMPLE')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_STREAMING')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=40)]")

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v.value = False
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(args, kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_COMMAND')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_IDLE')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=40)]")


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
            (next_state, result) = p._handler_unknown_discover(args, kwargs)
        except InstrumentStateException:
            ex_caught = True
        self.assertTrue(ex_caught)
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=40)]")
        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v = Mock(spec="val")

        v.value = True
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(args, kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_AUTOSAMPLE')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_STREAMING')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=40)]")

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v.value = False
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(args, kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_COMMAND')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_IDLE')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=40)]")



    def test_protocol_unknown_force_state(self):
        """
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol

        args = ['foo']
        kwargs = {'timeout': 30,}
        #kwargs =  dict({'timeout': 30,})
        ex_caught = False
        try:
            (next_state, result) = p._handler_unknown_force_state(args, kwargs)
        except InstrumentParameterException:
            ex_caught = True
        self.assertTrue(ex_caught)

        kwargs = dict({'timeout': 30,
                        'state': 'ARDVARK'})
        state = kwargs.get('state', None)
        print state

        (next_state, result) = p._handler_unknown_force_state(args, kwargs)
        self.assertEqual(next_state, 'ARDVARK')
        self.assertEqual(result, 'ARDVARK')


# create a mock instance of InstrumentDriver, and verify that the functions like
# start, settime, dd... pass the call to the proper mocked object.

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class InstrumentDriverIntFromIDK(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    ###
    #    Add instrument specific integration tests
    ###















    # assertParamDict is failing, needs a re-work





    def assertParamDict(self, pd, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """

        # Make it loop through once to warn with debugging of issues, 2nd time can send the exception
        # PARAMS is the master type list

        if all_params:
            log.debug("DICT 1 *********" + str(pd.keys()))
            log.debug("DICT 2 *********" + str(PARAMS.keys()))
            self.assertEqual(set(pd.keys()), set(PARAMS.keys()))

            for (key, type_val) in PARAMS.iteritems():
                self.assertTrue(isinstance(pd[key], type_val))
        else:
            for (key, val) in pd.iteritems():
                self.assertTrue(PARAMS.has_key(key))

                if val is not None: # If its not defined, lets just skip it, only catch wrong type assignments.
                    log.debug("Asserting that " + key +  " is of type " + str(PARAMS[key]))
                    self.assertTrue(isinstance(val, PARAMS[key]))
                else:
                    log.debug("*** Skipping " + key + " Because value is None ***")

    # need to rename this to a better name
    def assert_returned_parameters_match_set_parameters(self, params, reply):
        for label in params.keys():
            log.debug("ASSERTING " + label + " = " + str(params[label]) + " == " + str(reply[label]))
            try:
                self.assertEqual(params[label], reply[label])
            except:
                log.debug(label + " WAS NOT IN 'reply' " + str(reply))




    # WORKS
    def test_get_set(self):
        """
        Test device parameter access.
        """

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        #state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        #state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)
        
        reply = self.driver_client.cmd_dvr('discover_state')
        #reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        #state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)



        # Test 1 Conductivity = Y, small subset of possible parameters.

        log.debug("get/set Test 1 - Conductivity = Y, small subset of possible parameters.")
        params = {
            Parameter.CONDUCTIVITY : True,
            Parameter.PY1 : float(-3.859),
            Parameter.PY2 : float(-10.25),
            Parameter.PY3 : float(11.0),
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 2 - Conductivity = N, small subset of possible parameters.")
        params = {
            Parameter.CONDUCTIVITY : False,
            Parameter.PT4 : float(27.90597),
            Parameter.POFFSET : float(-0.1374),
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 3 - internal temperature sensor, small subset of possible parameters.")
        params = {
            Parameter.DS_DEVICE_DATE_TIME : time.strftime("%d %b %Y %H:%M:%S", time.localtime()),
            Parameter.PCALDATE : (2, 4, 2013),
            Parameter.TCALDATE : (2, 4, 2013),
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : False,
            Parameter.POFFSET : float(-0.1374),
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 4 - external temperature sensor, small subset of possible parameters.")
        params = {
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : True,
            Parameter.PD1 : float(50.02928),
            Parameter.PD2 : float(31.712),
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)

        log.debug("get/set Test 5 - get master set of possible parameters.")
        params = [
            # DC
            Parameter.PCALDATE,
            Parameter.PU0,
            Parameter.PY1,
            Parameter.PY2,
            Parameter.PY3,
            Parameter.PC1,
            Parameter.PC2,
            Parameter.PC3,
            Parameter.PD1,
            Parameter.PD2,
            Parameter.PT1,
            Parameter.PT2,
            Parameter.PT3,
            Parameter.PT4,
            Parameter.FACTORY_M,
            Parameter.FACTORY_B,
            Parameter.POFFSET,
            Parameter.TCALDATE,
            Parameter.TA0,
            Parameter.TA1,
            Parameter.TA2,
            Parameter.TA3,
            Parameter.CCALDATE,
            Parameter.CG,
            Parameter.CH,
            Parameter.CI,
            Parameter.CJ,
            Parameter.CTCOR,
            Parameter.CPCOR,
            Parameter.CSLOPE,

            # DS
            Parameter.DEVICE_VERSION,
            Parameter.SERIAL_NUMBER,
            Parameter.DS_DEVICE_DATE_TIME,
            Parameter.USER_INFO,
            Parameter.QUARTZ_PREASURE_SENSOR_SERIAL_NUMBER,
            Parameter.QUARTZ_PREASURE_SENSOR_RANGE,
            Parameter.EXTERNAL_TEMPERATURE_SENSOR,
            Parameter.CONDUCTIVITY,
            Parameter.IOP_MA,
            Parameter.VMAIN_V,
            Parameter.VLITH_V,
            Parameter.LAST_SAMPLE_P,
            Parameter.LAST_SAMPLE_T,
            Parameter.LAST_SAMPLE_S,

            # DS/SETSAMPLING
            Parameter.TIDE_INTERVAL,
            Parameter.TIDE_MEASUREMENT_DURATION,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS,
            Parameter.WAVE_SAMPLES_PER_BURST,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND,
            Parameter.USE_START_TIME,
            #Parameter.START_TIME,
            Parameter.USE_STOP_TIME,
            #Parameter.STOP_TIME,
            Parameter.TXWAVESTATS,
            Parameter.TIDE_SAMPLES_PER_DAY,
            Parameter.WAVE_BURSTS_PER_DAY,
            Parameter.MEMORY_ENDURANCE,
            Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE,
            Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS,
            Parameter.TOTAL_RECORDED_WAVE_BURSTS,
            Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START,
            Parameter.WAVE_BURSTS_SINCE_LAST_START,
            Parameter.TXREALTIME,
            Parameter.TXWAVEBURST,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC,
            Parameter.USE_MEASURED_TEMP_FOR_DENSITY_CALC,
            Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PREASURE_SENSOR,
            Parameter.AVERAGE_SALINITY_ABOVE_PREASURE_SENSOR,
            Parameter.PREASURE_SENSOR_HEIGHT_FROM_BOTTOM,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND,
            Parameter.MIN_ALLOWABLE_ATTENUATION,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM,
            Parameter.HANNING_WINDOW_CUTOFF,
            Parameter.SHOW_PROGRESS_MESSAGES,
            Parameter.STATUS,
            Parameter.LOGGING,
        ]

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)

        log.debug("get/set Test 6 - get master set of possible parameters using array containing Parameter.ALL")


        params3 = [
            Parameter.ALL
        ]

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 7 - Negative testing, broken values. Should get exception")
        params = {
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : 5,
            Parameter.PD1 : int(1),
            Parameter.PD2 : True,
        }
        exception = False
        try:
            reply = self.driver_client.cmd_dvr('set_resource', params)
        except InstrumentParameterException:
            exception = True
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
        self.assertTrue(exception)


        log.debug("get/set Test 9 - Negative testing, empty params dict")
        params = {
        }

        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 10 - Negative testing, None instead of dict")
        exception = False
        try:
            reply = self.driver_client.cmd_dvr('set_resource', None)
        except InstrumentParameterException:
            exception = True
        self.assertTrue(exception)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)



        log.debug("get/set Test N - Conductivity = Y, full set of set variables to known sane values.")
        params = {
            Parameter.DS_DEVICE_DATE_TIME : time.strftime("%d %b %Y %H:%M:%S", time.localtime()),
            Parameter.USER_INFO : "whoi",

            Parameter.PCALDATE : (2, 4, 2013),
            Parameter.PU0 : float(5.1),
            Parameter.PY1 : float(-3910.859),
            Parameter.PY2 : float(-10708.25),
            Parameter.PY3 : float(0.0),
            Parameter.PC1 : float(607.2786),
            Parameter.PC2 : float(1.0),
            Parameter.PC3 : float(-1024.374),
            Parameter.PD1 : float(0.02928),
            Parameter.PD2 : float(0.0),
            Parameter.PT1 : float(27.83369),
            Parameter.PT2 : float(0.607202),
            Parameter.PT3 : float(18.21885),
            Parameter.PT4 : float(27.90597),
            Parameter.POFFSET : float(-0.1374),
            Parameter.TCALDATE : (2, 4, 2013),

            # params that I had that appeared corrupted.
            #Parameter.TA0 : float(1.2),
            # I believe this was the origional value.
            Parameter.TA0 : float(1.2e-04),
            Parameter.TA1 : float(0.0002558291),
            Parameter.TA2 : float(-2.073449e-06),
            Parameter.TA3 : float(1.640089e-07),
            Parameter.CCALDATE : (28, 3, 2012),
            Parameter.CG : float(-10.25348),
            Parameter.CH : float(1.557569),
            Parameter.CI : float(-0.001737222),
            Parameter.CJ : float(0.0002268556),
            Parameter.CTCOR : float(3.25e-06),
            Parameter.CPCOR : float(-9.57e-08),
            Parameter.CSLOPE : float(1.0),
            Parameter.TXREALTIME : True,
            Parameter.TXWAVEBURST : True,
            Parameter.CONDUCTIVITY : True,
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : True,
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)


    # WORKS
    def test_set_sampling(self):
        """
        Test device setsampling.
        """
        parameter_all = [
            Parameter.ALL
        ]

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover_state')
        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        # Critical that for this test conductivity be in a known state.
        # Need to add a second testing section to test with Conductivity = False
        new_params = {
            Parameter.CONDUCTIVITY : True,
        }
        reply = self.driver_client.cmd_dvr('set_resource', new_params)

        # POSITIVE TESTING

        log.debug("setsampling Test 1 - TXWAVESTATS = N, small subset of possible parameters.")

        sampling_params = {
            Parameter.TIDE_INTERVAL : 9,
            Parameter.TXWAVESTATS : False,
            }

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        reply = self.driver_client.cmd_dvr(InstrumentCmds.SETSAMPLING, sampling_params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', parameter_all)


        return

        """
        Test 1: TXWAVESTATS = N
            Set:
                * Tide interval (integer minutes)
                    - Range 1 - 720
                * Tide measurement duration (seconds)
                    - Range: 10 - 43200 sec
                * Measure wave burst after every N tide samples
                    - Range 1 - 10,000
                * Number of wave samples per burst
                    - Range 4 - 60,000
                * wave sample duration
                    - Range [0.25, 0.5, 0.75, 1.0]
                * use start time
                    - Range [y, n]
                * use stop time
                    - Range [y, n]
                * TXWAVESTATS (real-time wave statistics)
        """

        log.debug("TEST 2 - TXWAVESTATS = N, full set of possible parameters")

        sampling_params = {
            Parameter.TIDE_INTERVAL : 9,
            Parameter.TIDE_MEASUREMENT_DURATION : 540,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1024,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(4.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : False,
        }

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        reply = self.driver_client.cmd_dvr(InstrumentCmds.SETSAMPLING, sampling_params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', parameter_all)

        """
        Test 2: TXWAVESTATS = Y
            Set:
                * Tide interval (integer minutes)
                    - Range 1 - 720
                * Tide measurement duration (seconds)
                    - Range: 10 - 43200 sec
                * Measure wave burst after every N tide samples
                    - Range 1 - 10,000
                * Number of wave samples per burst
                    - Range 4 - 60,000
                * wave sample duration
                    - Range [0.25, 0.5, 0.75, 1.0]
                    - USE WAVE_SAMPLES_SCANS_PER_SECOND instead
                      where WAVE_SAMPLES_SCANS_PER_SECOND = 1 / wave_sample_duration
                * use start time
                    - Range [y, n]
                * use stop time
                    - Range [y, n]
                * TXWAVESTATS (real-time wave statistics)
                    - Range [y, n]
                    OPTIONAL DEPENDING ON TXWAVESTATS
                    * Show progress messages
                      - Range [y, n]
                    * Number of wave samples per burst to use for wave
                      statistics
                      - Range > 512, power of 2...
                    * Use measured temperature and conductivity for
                      density calculation
                      - Range [y,n]
                    * Average water temperature above the pressure sensor
                      - Degrees C
                    * Height of pressure sensor from bottom
                      - Distance Meters
                    * Number of spectral estimates for each frequency
                      band
                      - You may have used Plan Deployment to determine
                        desired value
                    * Minimum allowable attenuation
                    * Minimum period (seconds) to use in auto-spectrum
                      Minimum of the two following
                      - frequency where (measured pressure / pressure at
                        surface) < (minimum allowable attenuation / wave
                        sample duration).
                      - (1 / minimum period). Frequencies > fmax are not
                        processed.
                    * Maximum period (seconds) to use in auto-spectrum
                       - ( 1 / maximum period). Frequencies < fmin are
                         not processed.
                    * Hanning window cutoff
                       - Hanning window suppresses spectral leakage that
                         occurs when time series to be Fourier transformed
                         contains periodic signal that does not correspond
                         to one of exact frequencies of FFT.
        """
        for x in range(0,3):
            log.debug("***")
        log.debug("TEST 2 - TXWAVESTATS = N")
        for x in range(0,3):
            log.debug("***")
        sampling_params = {
            Parameter.TIDE_INTERVAL : 18, #1,
            Parameter.TIDE_MEASUREMENT_DURATION : 1080,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1024,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(1.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : True,
            Parameter.SHOW_PROGRESS_MESSAGES : True,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : 512,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC : True,
            Parameter.PREASURE_SENSOR_HEIGHT_FROM_BOTTOM: 1.0,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND : 1,
            Parameter.MIN_ALLOWABLE_ATTENUATION : 1.0,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.HANNING_WINDOW_CUTOFF : 1.0
            }



        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        reply = self.driver_client.cmd_dvr(InstrumentCmds.SETSAMPLING, sampling_params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', parameter_all)

        """
        Test 3: These 2 prompts appears only if you enter N for using measured T and C for density calculation
                Average water temperature above the pressure sensor (Deg C) = 15.0, new value =
                Average salinity above the pressure sensor (PSU) = 35.0, new value =

        """
        for x in range(0,3):
            log.debug("***")
        log.debug("TEST 3 - TXWAVESTATS = N, USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC=N")
        for x in range(0,3):
            log.debug("***")
        sampling_params = {
            Parameter.TIDE_INTERVAL : 18, #4,
            Parameter.TIDE_MEASUREMENT_DURATION : 1080, #40,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1024,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(1.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : True,
            Parameter.SHOW_PROGRESS_MESSAGES : True,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : 512,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC : False,
            Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PREASURE_SENSOR : float(15.0),
            Parameter.AVERAGE_SALINITY_ABOVE_PREASURE_SENSOR : float(37.6),
            Parameter.PREASURE_SENSOR_HEIGHT_FROM_BOTTOM: 1.0,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND : 1,
            Parameter.MIN_ALLOWABLE_ATTENUATION : 1.0,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.HANNING_WINDOW_CUTOFF : 1.0
        }



        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        reply = self.driver_client.cmd_dvr(InstrumentCmds.SETSAMPLING, sampling_params)
        self.assertEqual(reply, None)

        # Alternate specification for all params
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        """

        Test 1B: TXWAVESTATS = N, NEGATIVE TESTING
            Set:
                * Tide interval (integer minutes)
                    - Range 1 - 720 (SEND OUT OF RANGE HIGH)
                * Tide measurement duration (seconds)
                    - Range: 10 - 43200 sec (SEND OUT OF RANGE LOW)
                * Measure wave burst after every N tide samples
                    - Range 1 - 10,000 (SEND OUT OF RANGE HIGH)
                * Number of wave samples per burst
                    - Range 4 - 60,000 (SEND OUT OF RANGE LOW)
                * wave sample duration
                    - Range [0.25, 0.5, 0.75, 1.0] (SEND OUT OF RANGE HIGH)
                    - USE WAVE_SAMPLES_SCANS_PER_SECOND instead
                      where WAVE_SAMPLES_SCANS_PER_SECOND = 1 / wave_sample_duration
                * use start time
                    - Range [y, n]
                * use stop time
                    - Range [y, n]
                * TXWAVESTATS (real-time wave statistics)
        """

        for x in range(0,30):
            log.debug("***")
        log.debug("Test 1B: TXWAVESTATS = N, NEGATIVE TESTING")
        log.debug("Need to decide to test and throw exception on out of range, or what?")
        for x in range(0,30):
            log.debug("***")
        sampling_params = {
            Parameter.TIDE_INTERVAL : 800,
            Parameter.TIDE_MEASUREMENT_DURATION : 1,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 20000,
            Parameter.WAVE_SAMPLES_PER_BURST : 1,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(2.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : False,
            }

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        exception = False
        try:
            reply = self.driver_client.cmd_dvr(InstrumentCmds.SETSAMPLING, sampling_params)
        except InstrumentParameterException:
            exception = True
        self.assertTrue(exception)

        reply = self.driver_client.cmd_dvr('get_resource', parameter_all)



    # WORKS
    def test_set_time(self):
        """
        Test setting time with settime command
        S>settime
        set current time:
        month (1 - 12) = 1
        day (1 - 31) = 1
        year (4 digits) = 1
        hour (0 - 23) = 1
        minute (0 - 59) = 1
        second (0 - 59) = 1

        time.strftime("%d %b %Y %H:%M:%S", time.localtime())
        """
        """
        Test device setsampling.
        """
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover_state')
        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        t = time.strftime("%d %b %Y %H:%M:%S", time.localtime())
        log.debug("t = " + str(t))
        reply = self.driver_client.cmd_dvr(InstrumentCmds.SET_TIME, t)

    # WORKS
    def test_upload_data_ascii(self):
        """
        Test device parameter access.
        """
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover_state')
        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        # Test the DD command.  Upload data in ASCII at baud set for general communication with Baud=
        reply = self.driver_client.cmd_dvr(InstrumentCmds.UPLOAD_DATA_ASCII_FORMAT)

        #log.debug(str(reply))
        (chunk, pat, reply) = reply.partition(NEWLINE)
        line = 0
        while len(chunk) == 12 or len(chunk) == 24:
            log.debug("Validating line #" + str(line) + " " + chunk)
            line = line + 1
            for c in chunk:
                self.assertTrue(c in '0123456789ABCDEF') # Only HEX CHARS ALLOWD
            (chunk, pat, reply) = reply.partition(NEWLINE)

        #log.debug("Remainder = " + repr(reply))
        self.assertEqual(reply, "")

    # WORKS
    def test_take_sample(self):
        """
        Test device parameter access.
        """
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover_state')
        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        # Test the DD command.  Upload data in ASCII at baud set for general communication with Baud=
        reply = self.driver_client.cmd_dvr(InstrumentCmds.TAKE_SAMPLE)
        log.debug("REPLY = " + str(reply))

    '''
    def test_baud_command(self):
        """
        Test baud command.
        """
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover_state')
        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        # Test that the device responds correctly to the baud command.
        # NOTE!! setting it to a baud that the tcp -> serial adapter is not
        # set to will require you to have to reconfigure the tcp -> serial
        # device to rescue the instrument.
        reply = self.driver_client.cmd_dvr(InstrumentCmds.BAUD, 9600)
        self.assertTrue(reply)
    '''

    # works
    def test_init_logging(self):
        """
        Test init logging command.
        """
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover_state')
        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)


        reply = self.driver_client.cmd_dvr(InstrumentCmds.INIT_LOGGING)

        self.assertTrue(reply)


    # works
    def test_quit_session(self):
        """
        Test quit session command.
        """
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover_state')
        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)



        # Note quit session just sleeps the device, so its safe to remain in COMMAND mode.
        reply = self.driver_client.cmd_dvr(InstrumentCmds.QUIT_SESSION)
        self.assertEqual(reply, None)
        state = self.driver_client.cmd_dvr('get_resource_state')
        log.debug("CURRENT STATE IS " + str(state))
        self.assertEqual(state, ProtocolState.COMMAND)

        # now can we return to command state?

        params = [
            Parameter.ALL
        ]
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertParamDict(reply)



###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class InstrumentDriverQualFromIDK(InstrumentDriverQualificationTestCase):
    def setUp(self):
        log.debug("BEFORE")
        InstrumentDriverQualificationTestCase.setUp(self)
        log.debug("AFTER")

    ###
    #    Add instrument specific qualification tests
    ###

    @patch.dict(CFG, {'endpoint':{'receive':{'timeout': 60}}})
    def test_autosample(self):
        """
        Test instrument driver execute interface to start and stop streaming
        mode.
        """

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)


        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)



        """
        # Make sure the sampling rate and transmission are sane.
        params = {
            SBE37Parameter.NAVG : 1,
            SBE37Parameter.INTERVAL : 5,
            SBE37Parameter.TXREALTIME : True
        }
        self.instrument_agent_client.set_param(params)
        """

        self.data_subscribers.no_samples = 2

        # Begin streaming.
        cmd = AgentCommand(command=ProtocolEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)

        non_accurate_seconds_count = 0
        while len(self.data_subscribers.samples_received) <= self.data_subscribers.no_samples and non_accurate_seconds_count < 1200:
            gevent.sleep(60)
            log.debug("SAMPLES RECEIVED => " + str(self.data_subscribers.__dict__)) # .keys()
            log.debug("EVENTS RECEIVED => " + str(self.event_subscribers.__dict__))

            non_accurate_seconds_count = non_accurate_seconds_count + 60

        # Halt streaming.
        cmd = AgentCommand(command=ProtocolEvent.STOP_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        # Assert we got some samples.
        #self.assertTrue(self.data_subscribers.samples_received > self.data_subscribers.no_samples)
        #self.assertTrue(non_accurate_seconds_count < 1200)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)


    def test_command_agent(self):
        """
        New test to learn how to talk to the new instrument agent
        Needs to have startup code modified...
        Example in extern/coi-services/ion/agents/instrument/test/test_instrument_agent.py
        """
        log.debug("**************1")
        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        log.debug("**************2")
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("**************3")
        #state = self._ia_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.IDLE)
        cmd = AgentCommand(command='get_resource_state')
        log.debug("**************4")
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("**************5")
        return

    @patch.dict(CFG, {'endpoint':{'receive':{'timeout': 2000}}})
    def test_direct_access_telnet_mode(self):
        """
        @brief This test verifies that the Instrument Driver
               properly supports direct access to the physical
               instrument. (telnet mode)
        """





        #see  nobska/mavs4 for examplar code in the main branch.



        cmd = AgentCommand(command='power_down')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_resource_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.POWERED_DOWN)

        cmd = AgentCommand(command='power_up')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_resource_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_resource_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.INACTIVE)
        log.debug("***********************************-2")
        cmd = AgentCommand(command='go_active')
        log.debug("***********************************-2.1")
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("***********************************-2.2")
        cmd = AgentCommand(command='get_resource_state')
        log.debug("***********************************-2.3")
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("***********************************-2.4")
        state = retval.result
        log.debug("***********************************-2.5")
        self.assertEqual(state, InstrumentAgentState.IDLE)
        log.debug("***********************************-1")
        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_resource_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)
        log.debug("***********************************0")
        # go direct access
        cmd = AgentCommand(command='go_direct_access',
            kwargs={'session_type': DirectAccessTypes.telnet,
                    #kwargs={'session_type':DirectAccessTypes.vsp,
                    'session_timeout':600,
                    'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))
        gevent.sleep(300)
        s = my_sock(retval.result['ip_address'], retval.result['port'])
        log.debug("***********************************1")
        try_count = 0
        while s.peek_at_buffer().find("Username: ") == -1:
            log.debug("WANT 'Username:' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(1)
            try_count = try_count + 1
            if try_count > 10:
                raise Timeout('I took longer than 10 seconds to get a Username: prompt')
        log.debug("***********************************2")
        s.remove_from_buffer("Username: ")
        s.send_data("bob\r\n", "1")

        try_count = 0
        while s.peek_at_buffer().find("token: ") == -1:
            log.debug("WANT 'token: ' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(0.1)
            try_count = try_count + 1
            if try_count > 10:
                raise Timeout('I took longer than 10 seconds to get a token: prompt')
        log.debug("***********************************3")
        s.remove_from_buffer("token: ")
        log.debug("***********************************3.1")
        s.send_data(retval.result['token'] + "\r\n", "1")
        log.debug("***********************************3.2")

        try_count = 0
        log.debug("***********************************3.3")
        while s.peek_at_buffer().find("connected\n") == -1:
            log.debug("***********************************3.4")
            log.debug("WANT 'connected\n' READ ==>" + str(s.peek_at_buffer()))
            log.debug("***********************************3.5")
            gevent.sleep(0.1)
            log.debug("***********************************3.6")
            s.peek_at_buffer()
            log.debug("***********************************3.7")
            try_count = try_count + 1
            log.debug("***********************************3.8")
            if try_count > 10:
                raise Timeout('I took longer than 10 seconds to get a connected prompt')
        log.debug("***********************************4")
        s.remove_from_buffer("connected\n")
        """
        s.send_data("ts\r\n", "1")
        log.debug("SENT THE TS COMMAND")

        pattern = re.compile("^([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9a-z]+),([ 0-9:]+)")

        matches = 0
        n = 0
        while n < 100:
            n = n + 1
            gevent.sleep(1)
            data = s.get_data()
            log.debug("READ ==>" + str(repr(data)))
            m = pattern.search(data)
            if m != None:
                matches = m.lastindex
                if matches == 7:
                    break

        self.assertTrue(matches == 7) # need to have found 7 conformant fields.
        """

    def test_get_capabilities(self):
        log.debug("********************************** IN test_get_capabilities ****************")
        #ResourceAgentEvent.GO_ACTIVE
        retval = self.instrument_agent_client.get_capabilities()
        log.debug("********************************** B ****************")
        for x in retval:
            log.debug(repr(x))
            log.debug(str(x))