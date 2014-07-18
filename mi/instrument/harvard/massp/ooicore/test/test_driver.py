"""
@package mi.instrument.harvard.massp.ooicore.test.test_driver
@file marine-integrations/mi/instrument/harvard/massp/ooicore/driver.py
@author Peter Cable
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

import re
import json
import time
from pprint import pformat
from collections import Counter
import unittest

import ntplib
import gevent
from nose.plugins.attrib import attr
from mock import Mock
from pyon.core.exception import ResourceError, BadRequest
from mi.core.exceptions import InstrumentCommandException
from mi.core.instrument.port_agent_client import PortAgentClient, PortAgentPacket
from mi.idk.comm_config import ConfigTypes
from mi.idk.unit_test import InstrumentDriverTestCase, LOCALHOST, ParameterTestConfigKey, AgentCapabilityType
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.core.instrument.instrument_driver import DriverConnectionState, DriverConfigKey, ResourceAgentState
from mi.core.instrument.instrument_driver import DriverProtocolState
from ion.agents.port.port_agent_process import PortAgentProcess
from mi.instrument.harvard.massp.ooicore.driver import InstrumentDriver, SlaveProtocol, NEWLINE
from mi.instrument.harvard.massp.ooicore.driver import DataParticleType
from mi.instrument.harvard.massp.ooicore.driver import ProtocolState
from mi.instrument.harvard.massp.ooicore.driver import ProtocolEvent
from mi.instrument.harvard.massp.ooicore.driver import Capability
from mi.instrument.harvard.massp.ooicore.driver import Parameter
from mi.instrument.harvard.massp.ooicore.driver import Protocol
from mi.instrument.harvard.massp.mcu.driver import Prompt as McuPrompt
import mi.instrument.harvard.massp.mcu.test.test_driver as mcu
import mi.instrument.harvard.massp.rga.test.test_driver as rga
import mi.instrument.harvard.massp.turbo.test.test_driver as turbo
from mi.core.log import get_logger


__author__ = 'Peter Cable'
__license__ = 'Apache 2.0'

log = get_logger()

massp_startup_config = {DriverConfigKey.PARAMETERS: {Parameter.SAMPLE_INTERVAL: 3600}}
massp_startup_config[DriverConfigKey.PARAMETERS].update(mcu.mcu_startup_config[DriverConfigKey.PARAMETERS])
massp_startup_config[DriverConfigKey.PARAMETERS].update(turbo.turbo_startup_config[DriverConfigKey.PARAMETERS])
massp_startup_config[DriverConfigKey.PARAMETERS].update(rga.rga_startup_config[DriverConfigKey.PARAMETERS])

###
#   Driver parameters for the tests
###

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.harvard.massp.ooicore.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id='4OW0M1',
    instrument_agent_name='harvard_massp_ooicore',
    instrument_agent_packet_config=DataParticleType(),
    driver_startup_config=massp_startup_config
)


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

# noinspection PyProtectedMember
class DriverTestMixinSub(DriverTestMixin):
    # Create some short names for the parameter test config
    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    STATES = ParameterTestConfigKey.STATES

    def get_sample_interval(self):
        one_minute = massp_startup_config[DriverConfigKey.PARAMETERS][mcu.Parameter.ONE_MINUTE]
        # turbo spin up time is fixed
        fixed_time = 60 * 15
        # sample time is variable, based on the value of one_minute
        sample_time = (one_minute / 1000.0) * 70
        return sample_time + fixed_time

    @staticmethod
    def send_port_agent_packet(protocol, data):
        """
        Send a port agent packet via got_data
        @param protocol Instrument Protocol instance
        @param data data to send
        """
        ts = ntplib.system_to_ntp_time(time.time())
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(data)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()

        # Push the response into the driver
        protocol.got_data(port_agent_packet)
        protocol.got_raw(port_agent_packet)
        log.debug('Sent port agent packet containing: %r', data)

    def send_side_effect(self, protocol, name):
        """
        Side effect function generator - will send responses based on input
        @param protocol Instrument protocol instance
        @returns side effect function
        """
        def inner(data):
            """
            Inner function for side effect generator
            @param data Data to send
            @returns length of response
            """
            my_response = str(self.responses[name].get(data.strip()))
            log.trace('my_send data: %r responses: %r', data, self.responses[name])
            if my_response is not None:
                log.trace("my_send: data: %r, my_response: %r", data, my_response)
                time.sleep(.1)
                if name == 'rga':
                    self.send_port_agent_packet(protocol, my_response + '\n' + NEWLINE)
                else:
                    self.send_port_agent_packet(protocol, my_response + NEWLINE)
                return len(my_response)

        return inner

    responses = {
        'mcu': {},
        'turbo': {},
        'rga': {},
    }

    _capabilities = {
        ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
        ProtocolState.COMMAND: ['DRIVER_EVENT_GET',
                                'DRIVER_EVENT_SET',
                                'DRIVER_EVENT_START_DIRECT',
                                'DRIVER_EVENT_START_AUTOSAMPLE',
                                'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                'DRIVER_EVENT_CALIBRATE',
                                'PROTOCOL_EVENT_ERROR',
                                'PROTOCOL_EVENT_POWEROFF',
                                'PROTOCOL_EVENT_START_NAFION_REGEN',
                                'PROTOCOL_EVENT_START_ION_REGEN',
                                'PROTOCOL_EVENT_START_MANUAL_OVERRIDE'],
        ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_STOP_AUTOSAMPLE',
                                   'PROTOCOL_EVENT_STOP',
                                   'PROTOCOL_EVENT_ERROR',
                                   'DRIVER_EVENT_ACQUIRE_SAMPLE'],
        ProtocolState.ERROR: ['PROTOCOL_EVENT_CLEAR'],
        ProtocolState.POLL: ['PROTOCOL_EVENT_STOP', 'PROTOCOL_EVENT_ERROR'],
        ProtocolState.CALIBRATE: ['PROTOCOL_EVENT_STOP', 'PROTOCOL_EVENT_ERROR'],
        ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT'],
        ProtocolState.REGEN: ['PROTOCOL_EVENT_STOP_REGEN',
                              'PROTOCOL_EVENT_ERROR',
                              'PROTOCOL_EVENT_REGEN_COMPLETE'],
        ProtocolState.MANUAL_OVERRIDE: ['PROTOCOL_EVENT_STOP_MANUAL_OVERRIDE',
                                        'PROTOCOL_EVENT_GET_SLAVE_STATES',
                                        'DRIVER_EVENT_CALIBRATE',
                                        'PROTOCOL_EVENT_START1',
                                        'PROTOCOL_EVENT_START2',
                                        'PROTOCOL_EVENT_SAMPLE',
                                        'PROTOCOL_EVENT_NAFREG',
                                        'PROTOCOL_EVENT_IONREG',
                                        'PROTOCOL_EVENT_STANDBY',
                                        'PROTOCOL_EVENT_POWEROFF',
                                        'PROTOCOL_EVENT_CLEAR',
                                        'DRIVER_EVENT_ACQUIRE_STATUS',
                                        'PROTOCOL_EVENT_START_TURBO',
                                        'PROTOCOL_EVENT_STOP_TURBO',
                                        'PROTOCOL_EVENT_START_SCAN',
                                        'PROTOCOL_EVENT_STOP_SCAN'],
    }

    _driver_parameters = {
        Parameter.SAMPLE_INTERVAL: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
    }

    _driver_parameters.update(mcu.DriverTestMixinSub._driver_parameters)
    _driver_parameters.update(rga.DriverTestMixinSub._driver_parameters)
    _driver_parameters.update(turbo.DriverTestMixinSub._driver_parameters)

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.CALIBRATE: {STATES: [ProtocolState.COMMAND, ProtocolState.MANUAL_OVERRIDE]},
        Capability.CLEAR: {STATES: [ProtocolState.ERROR, ProtocolState.MANUAL_OVERRIDE]},
        Capability.POWEROFF: {STATES: [ProtocolState.COMMAND, ProtocolState.MANUAL_OVERRIDE]},

        Capability.START_AUTOSAMPLE: {STATES: [ProtocolState.COMMAND]},
        Capability.ACQUIRE_SAMPLE: {STATES: [ProtocolState.COMMAND]},
        Capability.START_ION: {STATES: [ProtocolState.COMMAND]},
        Capability.START_NAFION: {STATES: [ProtocolState.COMMAND]},
        Capability.STOP_AUTOSAMPLE: {STATES: [ProtocolState.AUTOSAMPLE]},

        Capability.ACQUIRE_STATUS: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
        Capability.START1: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
        Capability.START2: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
        Capability.SAMPLE: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
        Capability.START_TURBO: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
        Capability.STOP_TURBO: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
        Capability.START_SCAN: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
        Capability.STOP_SCAN: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
        Capability.IONREG: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
        Capability.NAFREG: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
        Capability.STANDBY: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
        Capability.STOP_REGEN: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
        Capability.GET_SLAVE_STATES: {STATES: [ProtocolState.MANUAL_OVERRIDE]},
    }


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
# noinspection PyProtectedMember
@attr('UNIT', group='mi')
class DriverUnitTest(InstrumentDriverUnitTestCase, DriverTestMixinSub):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def assert_initialize_driver(self, driver, initial_protocol_state=DriverProtocolState.COMMAND):
        """
        Initialize an instrument driver with a mock port agent.  This will allow us to test the
        got data method.  Will the instrument, using test mode, through it's connection state
        machine.  End result, the driver will be in test mode and the connection state will be
        connected.
        @param driver: Instrument driver instance.
        @param initial_protocol_state: the state to force the driver too
        """
        # Put the driver into test mode
        driver.set_test_mode(True)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)

        # Now configure the driver with the mock_port_agent, verifying
        # that the driver transitions to that state
        config = {'mcu': {'mock_port_agent': Mock(spec=PortAgentClient)},
                  'rga': {'mock_port_agent': Mock(spec=PortAgentClient)},
                  'turbo': {'mock_port_agent': Mock(spec=PortAgentClient)}}
        driver.configure(config=config)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)

        # Invoke the connect method of the driver: should connect to mock
        # port agent.  Verify that the connection FSM transitions to CONNECTED,
        # (which means that the FSM should now be reporting the ProtocolState).
        driver.connect()
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        # add a send side effect for each port agent
        for slave in SlaveProtocol.list():
            protocol = driver._slave_protocols[slave]
            if slave == 'mcu':
                protocol.set_init_params(mcu.mcu_startup_config)
                self.responses[slave] = mcu.DriverTestMixinSub.responses
            elif slave == 'rga':
                protocol.set_init_params(rga.rga_startup_config)
                self.responses[slave] = rga.DriverTestMixinSub.responses
            elif slave == 'turbo':
                protocol.set_init_params(turbo.turbo_startup_config)
                self.responses[slave] = turbo.DriverTestMixinSub.responses
            protocol._connection.send.side_effect = self.send_side_effect(protocol, slave)
            protocol._init_params()

        driver._protocol._param_dict.set_value(Parameter.SAMPLE_INTERVAL,
                                               massp_startup_config['parameters'][Parameter.SAMPLE_INTERVAL])

        # Force the instrument into a known state
        self.assert_force_state(driver, initial_protocol_state)
        self.assert_force_all_slave_states(driver, ProtocolState.COMMAND)

    def assert_force_all_slave_states(self, driver, protocol_state):
        for slave in SlaveProtocol.list():
            self.assert_force_slave_state(driver, slave, protocol_state)

    def assert_force_slave_state(self, driver, name, protocol_state):
        driver._slave_protocols[name]._protocol_fsm.current_state = protocol_state

    def assert_protocol_state_change(self, protocol, target_state, timeout=1):
        end_time = time.time() + timeout
        sleep_time = timeout / 20.0
        while True:
            if protocol.get_current_state() == target_state:
                return
            log.debug('assert_protocol_state_change -- state: %s target_state: %s',
                      protocol.get_current_state(), target_state)
            time.sleep(sleep_time)
            self.assertGreaterEqual(end_time, time.time(), msg='Failed to transition states within timeout')

    def assert_sequence_handling(self, event):
        """
        Test the state transitions for these events.
        """
        # this test is only valid for these events...
        self.assertIn(event, [Capability.ACQUIRE_SAMPLE, Capability.START_AUTOSAMPLE, Capability.CALIBRATE])

        driver = self.test_connect()
        slaves = driver._slave_protocols

        self.clear_data_particle_queue()

        # start autosample
        driver._protocol._protocol_fsm.on_event(event)

        # sleep to let protocol move the FSM to the correct state
        # loop, because the monkey patched time doesn't reliably sleep long enough...
        now = time.time()
        while time.time() < (now+3):
            time.sleep(1)

        # master protocol sends START1 to mcu at start of sample, send response.
        self.send_port_agent_packet(driver._slave_protocols['mcu'], McuPrompt.START1 + NEWLINE)

        # modify turbo responses to indicate turbo is up to speed
        self.responses['turbo'] = turbo.DriverTestMixinSub.responses_at_speed

        # turbo should move to AT_SPEED
        self.assert_protocol_state_change(slaves['turbo'], turbo.ProtocolState.AT_SPEED, 15)

        # master protocol sends START2, mcu moves to START2, send response.
        self.assert_protocol_state_change(slaves['mcu'], mcu.ProtocolState.START2, 2)
        self.send_port_agent_packet(driver._slave_protocols['mcu'], McuPrompt.START2 + NEWLINE)

        # rga should move to SCAN
        self.assert_protocol_state_change(slaves['rga'], rga.ProtocolState.SCAN, 2)

        if event == Capability.CALIBRATE:
            # master protocol sends CAL, mcu moves to CAL
            self.assert_protocol_state_change(slaves['mcu'], mcu.ProtocolState.CALIBRATE, 10)
            # simulate calibrate complete, send calibrate finished
            self.send_port_agent_packet(driver._slave_protocols['mcu'], McuPrompt.CAL_FINISHED + NEWLINE)
        else:
            # master protocol sends SAMPLE, mcu moves to SAMPLE
            self.assert_protocol_state_change(slaves['mcu'], mcu.ProtocolState.SAMPLE, 10)
            # simulate sample complete, send sample finished
            self.send_port_agent_packet(driver._slave_protocols['mcu'], McuPrompt.SAMPLE_FINISHED + NEWLINE)

        # turbo moves to SPINNING_DOWN
        self.assert_protocol_state_change(slaves['turbo'], turbo.ProtocolState.SPINNING_DOWN, 15)

        # swap turbo responses to stopped
        self.responses['turbo'] = turbo.DriverTestMixinSub.responses_stopped

        # all three slave protocols should move to COMMAND
        self.assert_protocol_state_change(slaves['turbo'], turbo.ProtocolState.COMMAND, 15)
        self.assert_protocol_state_change(slaves['mcu'], turbo.ProtocolState.COMMAND, 15)
        self.assert_protocol_state_change(slaves['rga'], turbo.ProtocolState.COMMAND, 15)

        # send a couple of data telegrams to the mcu, to verify particles are generated
        self.send_port_agent_packet(slaves['mcu'], mcu.TELEGRAM_1 + NEWLINE)
        self.send_port_agent_packet(slaves['mcu'], mcu.TELEGRAM_2 + NEWLINE)

        if event == Capability.START_AUTOSAMPLE:
            self.assertEqual(driver._protocol.get_current_state(), ProtocolState.AUTOSAMPLE)
        else:
            self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

        particles = Counter()
        for p in self._data_particle_received:
            particle_dict = json.loads(p)
            stream_type = particle_dict.get('stream_name')
            self.assertIsNotNone(stream_type)
            particles[stream_type] += 1

        log.debug('Particles generated: %r', particles)
        # verify we have received at least one of each particle type
        for particle_type in DataParticleType.list():
            self.assertGreaterEqual(particles[particle_type], 1)

    def test_connect(self, *args, **kwargs):
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, *args, **kwargs)
        return driver

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilities
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        # self.assert_enum_has_no_duplicates(InstrumentCommand())

        # Test capabilities for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, self._capabilities)

    def test_poll(self):
        self.assert_sequence_handling(Capability.ACQUIRE_SAMPLE)

    def test_autosample(self):
        self.assert_sequence_handling(Capability.START_AUTOSAMPLE)

    def test_calibrate(self):
        self.assert_sequence_handling(Capability.CALIBRATE)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
        protocol = Protocol(mock_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        self.maxDiff = None
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)

    def test_manual_override(self):
        """
        test the manual override state
        """
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(Capability.START_MANUAL)

        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.MANUAL_OVERRIDE)

        driver._protocol._protocol_fsm.on_event(Capability.START1)
        self.send_port_agent_packet(driver._slave_protocols['mcu'], McuPrompt.START1 + NEWLINE)

        driver._protocol._protocol_fsm.on_event(Capability.START_TURBO)

        self.responses['turbo'] = turbo.DriverTestMixinSub.responses_at_speed

        driver._protocol._protocol_fsm.on_event(Capability.START_SCAN)
        driver._protocol._protocol_fsm.on_event(Capability.STOP_SCAN)

        driver._protocol._protocol_fsm.on_event(Capability.STOP_TURBO)

        self.responses['turbo'] = turbo.DriverTestMixinSub.responses_stopped

        driver._protocol._protocol_fsm.on_event(Capability.STOP_MANUAL)

        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
#                                                                             #
#    NOTE: execute U SETMINUTE01000 on the MCU prior to running these tests   #
#                                                                             #
###############################################################################
# noinspection PyMethodMayBeStatic,PyAttributeOutsideInit
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, DriverTestMixinSub):
    def setUp(self):
        self.port_agents = {}
        InstrumentDriverIntegrationTestCase.setUp(self)

    def init_port_agent(self):
        """
        Launch the driver process and driver client.  This is used in the
        integration and qualification tests.  The port agent abstracts the physical
        interface with the instrument.
        @returns pid to the logger process
        """
        if self.port_agents:
            log.error("Port agent already initialized")
            return

        log.debug("Startup Port Agent")

        config = self.port_agent_config()
        log.debug("port agent config: %s", config)

        port_agents = {}

        if config['instrument_type'] != ConfigTypes.MULTI:
            config = {'only one port agent here!': config}
        for name, each in config.items():
            if type(each) != dict:
                continue
            port_agent_host = each.get('device_addr')
            if port_agent_host is not None:
                port_agent = PortAgentProcess.launch_process(each, timeout=60, test_mode=True)

                port = port_agent.get_data_port()
                pid = port_agent.get_pid()

                if port_agent_host == LOCALHOST:
                    log.info('Started port agent pid %s listening at port %s' % (pid, port))
                else:
                    log.info("Connecting to port agent on host: %s, port: %s", port_agent_host, port)
                port_agents[name] = port_agent

        self.addCleanup(self.stop_port_agent)
        self.port_agents = port_agents

    def stop_port_agent(self):
        """
        Stop the port agent.
        """
        log.info("Stop port agent")
        if self.port_agents:
            log.debug("found port agents, now stop them")
            for agent in self.port_agents.values():
                agent.stop()
        self.port_agents = {}

    def port_agent_comm_config(self):
        """
        Generate the port agent comm config from the port agents
        @return config
        """
        config = {}
        for name, each in self.port_agents.items():
            port = each.get_data_port()
            cmd_port = each.get_command_port()

            config[name] = {
                'addr': each._config['port_agent_addr'],
                'port': port,
                'cmd_port': cmd_port
            }
        return config

    def assert_slave_state(self, name, state, timeout=30, sleep_time=.5, command_ok=False):
        end_time = time.time() + timeout
        while True:
            if command_ok and self.driver_client.cmd_dvr('get_resource_state') == ProtocolState.COMMAND:
                return
            _, states = self.driver_client.cmd_dvr('execute_resource', Capability.GET_SLAVE_STATES)
            if states.get(name) == state:
                return
            self.assertGreater(end_time, time.time(),
                               msg='Slave protocol [%s] failed to transition to %s before timeout' % (name, state))
            log.debug('Failed to achieve target slave [%s] state: %s.  Sleeping [%5.2fs left]',
                      name, state, end_time - time.time())
            time.sleep(sleep_time)

    def test_driver_process(self):
        """
        Test for correct launch of driver process and communications, including asynchronous driver events.
        Overridden to support multiple port agents.
        """
        log.info("Ensuring driver process was started properly ...")

        # Verify processes exist.
        self.assertNotEqual(self.driver_process, None)
        drv_pid = self.driver_process.getpid()
        self.assertTrue(isinstance(drv_pid, int))

        self.assertNotEqual(self.port_agents, None)
        for port_agent in self.port_agents.values():
            pagent_pid = port_agent.get_pid()
            self.assertTrue(isinstance(pagent_pid, int))

        # Send a test message to the process interface, confirm result.
        log.debug("before 'process_echo'")
        reply = self.driver_client.cmd_dvr('process_echo')
        log.debug("after 'process_echo'")
        self.assert_(reply.startswith('ping from resource ppid:'))

        reply = self.driver_client.cmd_dvr('driver_ping', 'foo')
        self.assert_(reply.startswith('driver_ping: foo'))

        # Test the event thread publishes and client side picks up events.
        events = [
            'I am important event #1!',
            'And I am important event #2!'
        ]
        self.driver_client.cmd_dvr('test_events', events=events)
        gevent.sleep(1)

        # Confirm the events received are as expected.
        self.assertEqual(self.events, events)

        # Test the exception mechanism.
        with self.assertRaises(ResourceError):
            exception_str = 'Oh no, something bad happened!'
            self.driver_client.cmd_dvr('test_exceptions', exception_str)

    def test_get_parameters(self):
        """
        Test get action for all parameters
        """
        self.assert_initialize_driver()
        for key, value in massp_startup_config[DriverConfigKey.PARAMETERS].iteritems():
            self.assert_get(key, value)

    def test_set_parameters(self):
        """
        Test set action for all parameters
        """
        self.assert_initialize_driver()

        parameters = Parameter.dict()
        parameters.update(turbo.Parameter.dict())
        parameters.update(rga.Parameter.dict())
        parameters.update(mcu.Parameter.dict())

        constraints = turbo.ParameterConstraints.dict()
        constraints.update(rga.ParameterConstraints.dict())

        for name, parameter in parameters.iteritems():
            value = massp_startup_config[DriverConfigKey.PARAMETERS].get(parameter)
            # do we have a value to set?
            if value is not None:
                # is the parameter RW?
                if not self._driver_parameters[parameter][self.READONLY]:
                    # is there a constraint for this parameter?
                    if name in constraints:
                        _, minimum, maximum = constraints[name]
                        # set within constraints
                        self.assert_set(parameter, minimum + 1)
                    else:
                        # set to startup value + 1
                        self.assert_set(parameter, value + 1)
                else:
                    # readonly, assert exception on set
                    self.assert_set_exception(parameter)

    def test_set_bogus_parameter(self):
        """
        Verify setting a bad parameter raises an exception
        """
        self.assert_initialize_driver()
        self.assert_set_exception('BOGUS', 'CHEESE')

    def test_out_of_range(self):
        """
        Verify setting parameters out of range raises exceptions
        """
        self.assert_initialize_driver()
        parameters = Parameter.dict()
        parameters.update(turbo.Parameter.dict())
        parameters.update(rga.Parameter.dict())
        parameters.update(mcu.Parameter.dict())

        constraints = turbo.ParameterConstraints.dict()
        constraints.update(rga.ParameterConstraints.dict())

        log.debug('Testing out of range values.')
        log.debug('Parameters: %s', pformat(parameters))
        log.debug('Constraints: %s', pformat(constraints))

        for parameter in constraints:
            param = parameters[parameter]
            if not self._driver_parameters[param][self.READONLY]:
                _, minimum, maximum = constraints[parameter]
                self.assert_set_exception(param, minimum - 1)
                self.assert_set_exception(param, maximum + 1)
                self.assert_set_exception(param, "strings aren't valid here!")

    def test_bad_command(self):
        """
        Verify sending a bad command raises an exception
        """
        self.assert_initialize_driver()
        self.assert_driver_command_exception('BAD_COMMAND', exception_class=InstrumentCommandException)

    def test_incomplete_config(self):
        """
        Break our startup config, then verify the driver raises an exception
        """
        # grab the old config
        startup_params = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
        old_value = startup_params[rga.Parameter.EE]
        failed = False

        try:
            # delete a required parameter
            del (startup_params[rga.Parameter.EE])
            # re-init to take our broken config
            self.init_driver_process_client()
            self.assert_initialize_driver()
            failed = True
        except ResourceError as e:
            log.info('Exception thrown, test should pass: %r', e)
        finally:
            startup_params[rga.Parameter.EE] = old_value

        if failed:
            self.fail('Failed to throw exception on missing parameter')

    def test_acquire_sample(self):
        """
        Verify the acquire sample command
        Particles are tested elsewhere, so skipped here.
        """
        self.assert_initialize_driver()
        self.assert_driver_command(Capability.ACQUIRE_SAMPLE, state=ProtocolState.POLL)
        self.assert_state_change(ProtocolState.COMMAND, self.get_sample_interval())

    def test_autosample(self):
        """
        Start autosample, verify we generate three RGA status particles, indicating two
        complete sampling cycles and the start of a third...
        """
        num_samples = 2
        self.assert_initialize_driver()
        self.assert_set(rga.Parameter.NF, 6)
        self.assert_set(Parameter.SAMPLE_INTERVAL, self.get_sample_interval())
        self.assert_driver_command(Capability.START_AUTOSAMPLE)
        self.assert_async_particle_generation(rga.DataParticleType.RGA_STATUS, Mock(),
                                              particle_count=num_samples,
                                              timeout=self.get_sample_interval() * num_samples)
        self.assert_driver_command(Capability.STOP_AUTOSAMPLE)
        self.assert_state_change(ProtocolState.COMMAND, timeout=self.get_sample_interval())

    def test_nafreg(self):
        """
        Verify Nafion Regeneration sequence
        This runs about 2 hours with "normal" timing, should be a few minutes as configured.
        May throw an exception due to short run time, as the target temperature may not be achieved.
        """
        self.assert_initialize_driver()
        self.assert_driver_command(Capability.START_NAFION)
        self.assert_state_change(ProtocolState.REGEN, 10)
        self.assert_state_change(ProtocolState.COMMAND, 600)

    def test_ionreg(self):
        """
        Verify Ion Chamber Regeneration sequence
        This runs about 2 hours with "normal" timing, should be a few minutes as configured.
        May throw an exception due to short run time, as the target temperature may not be achieved.
        """
        self.assert_initialize_driver()
        self.assert_driver_command(Capability.START_ION)
        self.assert_state_change(ProtocolState.REGEN, 10)
        self.assert_state_change(ProtocolState.COMMAND, 600)

    def test_manual_override(self):
        """
        Test the manual override mode.  Verify we can go through an entire sample sequence manually.
        """
        self.assert_initialize_driver()
        self.assert_driver_command(Capability.START_MANUAL, state=ProtocolState.MANUAL_OVERRIDE)
        self.assert_driver_command(Capability.START1)
        self.assert_slave_state('mcu', mcu.ProtocolState.WAITING_TURBO, timeout=90, sleep_time=2)
        self.assert_driver_command(Capability.START_TURBO)
        self.assert_slave_state('turbo', turbo.ProtocolState.AT_SPEED, timeout=600, sleep_time=10)
        self.assert_driver_command(Capability.START2)
        self.assert_slave_state('mcu', mcu.ProtocolState.WAITING_RGA, timeout=600, sleep_time=10)
        self.assert_driver_command(Capability.START_SCAN)
        self.assert_slave_state('rga', rga.ProtocolState.SCAN, timeout=60, sleep_time=1)
        self.assert_driver_command(Capability.SAMPLE)
        self.assert_slave_state('mcu', mcu.ProtocolState.SAMPLE, timeout=60, sleep_time=1)
        self.assert_slave_state('mcu', mcu.ProtocolState.STOPPING, timeout=600, sleep_time=10)
        self.assert_driver_command(Capability.STOP_SCAN)
        self.assert_slave_state('rga', rga.ProtocolState.COMMAND, timeout=60, sleep_time=1)
        self.assert_driver_command(Capability.STOP_TURBO)
        self.assert_slave_state('turbo', turbo.ProtocolState.SPINNING_DOWN, timeout=60, sleep_time=1)
        self.assert_slave_state('turbo', turbo.ProtocolState.COMMAND, timeout=600, sleep_time=10)
        self.assert_driver_command(Capability.STANDBY)
        self.assert_slave_state('mcu', mcu.ProtocolState.COMMAND, timeout=600, sleep_time=10)
        self.assert_driver_command(Capability.STOP_MANUAL, state=ProtocolState.COMMAND)

    def test_exit_manual_override(self):
        """
        Test that we when we exit manual override in sequence, all slave protocols return to COMMAND
        """
        self.assert_initialize_driver()
        self.assert_driver_command(Capability.START_MANUAL, state=ProtocolState.MANUAL_OVERRIDE)
        self.assert_driver_command(Capability.START1)
        self.assert_slave_state('mcu', mcu.ProtocolState.WAITING_TURBO, timeout=90, sleep_time=2)
        self.assert_driver_command(Capability.START_TURBO)
        self.assert_slave_state('turbo', turbo.ProtocolState.AT_SPEED, timeout=600, sleep_time=10)
        self.assert_driver_command(Capability.START2)
        self.assert_slave_state('mcu', mcu.ProtocolState.WAITING_RGA, timeout=600, sleep_time=10)
        self.assert_driver_command(Capability.START_SCAN)
        self.assert_slave_state('rga', rga.ProtocolState.SCAN, timeout=60, sleep_time=1)
        self.assert_driver_command(Capability.SAMPLE)
        self.assert_slave_state('mcu', mcu.ProtocolState.SAMPLE, timeout=60, sleep_time=1)
        self.assert_driver_command(Capability.STOP_MANUAL)
        self.assert_state_change(ProtocolState.COMMAND, timeout=120)
        self.assert_slave_state('rga', rga.ProtocolState.COMMAND, command_ok=True)
        self.assert_slave_state('turbo', turbo.ProtocolState.COMMAND, command_ok=True)
        self.assert_slave_state('mcu', mcu.ProtocolState.COMMAND, command_ok=True)

    @unittest.skip('Test runs approximately 1 hour')
    def test_full_sample(self):
        """
        Run a sample with the "normal" timing
        """
        # grab the old config
        startup_params = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
        old_value = startup_params[mcu.Parameter.ONE_MINUTE]
        failed = False

        try:
            startup_params[mcu.Parameter.ONE_MINUTE] = 60000
            # re-init to take our new config
            self.init_driver_process_client()
            self.test_acquire_sample()

        except Exception as e:
            failed = True
            log.info('Exception thrown, test should fail: %r', e)
        finally:
            startup_params[mcu.Parameter.ONE_MINUTE] = old_value

        if failed:
            self.fail('Failed to acquire sample with normal timing')


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
# noinspection PyMethodMayBeStatic,PyAttributeOutsideInit,PyProtectedMember
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase, DriverTestMixinSub):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def init_port_agent(self):
        """
        Launch the driver process and driver client.  This is used in the
        integration and qualification tests.  The port agent abstracts the physical
        interface with the instrument.
        @return pid to the logger process
        """
        if self.port_agent:
            log.error("Port agent already initialized")
            return

        log.debug("Startup Port Agent")

        config = self.port_agent_config()
        log.debug("port agent config: %s", config)

        port_agents = {}

        if config['instrument_type'] != ConfigTypes.MULTI:
            config = {'only one port agent here!': config}
        for name, each in config.items():
            if type(each) != dict:
                continue
            port_agent_host = each.get('device_addr')
            if port_agent_host is not None:
                port_agent = PortAgentProcess.launch_process(each, timeout=60, test_mode=True)

                port = port_agent.get_data_port()
                pid = port_agent.get_pid()

                if port_agent_host == LOCALHOST:
                    log.info('Started port agent pid %s listening at port %s' % (pid, port))
                else:
                    log.info("Connecting to port agent on host: %s, port: %s", port_agent_host, port)
                port_agents[name] = port_agent

        self.addCleanup(self.stop_port_agent)
        self.port_agents = port_agents

    def stop_port_agent(self):
        """
        Stop the port agent.
        """
        log.info("Stop port agent")
        if self.port_agents:
            log.debug("found port agents, now stop them")
            for agent in self.port_agents.values():
                agent.stop()
        self.port_agents = {}

    def port_agent_comm_config(self):
        """
        Generate the port agent comm config from the port agents
        @return config
        """
        config = {}
        for name, each in self.port_agents.items():
            port = each.get_data_port()
            cmd_port = each.get_command_port()

            config[name] = {
                'addr': each._config['port_agent_addr'],
                'port': port,
                'cmd_port': cmd_port
            }
        return config

    def init_instrument_agent_client(self):
        """
        Overridden to handle multiple port agent config
        """
        log.info("Start Instrument Agent Client")

        # Driver config
        driver_config = {
            'dvr_mod': self.test_config.driver_module,
            'dvr_cls': self.test_config.driver_class,
            'workdir': self.test_config.working_dir,
            'process_type': (self.test_config.driver_process_type,),
            'comms_config': self.port_agent_comm_config(),
            'startup_config': self.test_config.driver_startup_config
        }

        # Create agent config.
        agent_config = {
            'driver_config': driver_config,
            'stream_config': self.data_subscribers.stream_config,
            'agent': {'resource_id': self.test_config.agent_resource_id},
            'test_mode': True  # Enable a poison pill. If the spawning process dies
            ## shutdown the daemon process.
        }

        log.debug("Agent Config: %s", agent_config)

        # Start instrument agent client.
        self.instrument_agent_manager.start_client(
            name=self.test_config.agent_name,
            module=self.test_config.agent_module,
            cls=self.test_config.agent_class,
            config=agent_config,
            resource_id=self.test_config.agent_resource_id,
            deploy_file=self.test_config.container_deploy_file
        )

        self.instrument_agent_client = self.instrument_agent_manager.instrument_agent_client

    def assert_da_command(self, command, response=None, max_retries=None):
        """
        Assert direct access command returns the expected response
        @param command: command to send
        @param response: expected response
        @param max_retries: maximum number of retries
        @return: result of command
        """
        self.tcp_client.send_data(command + NEWLINE)
        if response:
            if max_retries:
                result = self.tcp_client.expect_regex(response, max_retries=max_retries)
            else:
                result = self.tcp_client.expect_regex(response)
            self.assertTrue(result)
            return result

    def test_discover(self):
        """
        Overridden because we do not discover to autosample.
        """
        # Verify the agent is in command mode
        self.assert_enter_command_mode()

        # Now reset and try to discover.  This will stop the driver which holds the current
        # instrument state.
        self.assert_reset()
        self.assert_discover(ResourceAgentState.COMMAND)

    def test_direct_access_telnet_mode(self):
        """
        This test manually tests that the Instrument Driver properly supports
        direct access to the physical instrument. (telnet mode)

        We want to verify direct access to all three parts of the instrument, so we'll need
        to go through most of the sample sequence
        """
        _turbo = 'turbo:'
        _mcu = 'mcu:'
        _rga = 'rga:'
        q_current = _turbo + turbo.DriverTestMixinSub.query_current
        q_voltage = _turbo + turbo.DriverTestMixinSub.query_voltage
        q_bearing = _turbo + turbo.DriverTestMixinSub.query_temp_bearing
        q_motor = _turbo + turbo.DriverTestMixinSub.query_temp_motor
        q_speed = _turbo + turbo.DriverTestMixinSub.query_speed_actual

        turbo_response = re.compile('\d{10}(\d{6})\d{3}\r')

        self.assert_direct_access_start_telnet(session_timeout=6000, inactivity_timeout=120)
        self.assertTrue(self.tcp_client)

        # start1
        self.assert_da_command(_mcu + mcu.InstrumentCommand.BEAT, '(%s)' % mcu.Prompt.BEAT)
        self.assert_da_command(_mcu + mcu.InstrumentCommand.START1, '(%s)' % mcu.Prompt.START1, max_retries=60)

        # sleep a bit to give the turbo time to power on
        time.sleep(20)

        # spin up the turbo
        self.assert_da_command(_turbo + turbo.DriverTestMixinSub.set_station_on,
                               turbo.DriverTestMixinSub.set_station_on)
        self.assert_da_command(_turbo + turbo.DriverTestMixinSub.set_pump_on,
                               turbo.DriverTestMixinSub.set_pump_on)

        for x in range(20):
            current = int(self.assert_da_command(q_current, turbo_response).group(1))
            voltage = int(self.assert_da_command(q_voltage, turbo_response).group(1))
            bearing = int(self.assert_da_command(q_bearing, turbo_response).group(1))
            motor = int(self.assert_da_command(q_motor, turbo_response).group(1))
            speed = int(self.assert_da_command(q_speed, turbo_response).group(1))
            log.debug('current: %d voltage: %d bearing: %d motor: %d speed: %d',
                      current, voltage, bearing, motor, speed)
            if speed > 90000:
                break
            time.sleep(5)

        # turbo is up to speed, send START2
        self.assert_da_command(_mcu + mcu.InstrumentCommand.BEAT, '(%s)' % mcu.Prompt.BEAT)
        self.assert_da_command(_mcu + mcu.InstrumentCommand.START2, '(%s)' % mcu.Prompt.START2, max_retries=120)

        # sleep for a bit for the RGA to turn on
        time.sleep(5)

        result = self.assert_da_command(_rga + rga.InstrumentCommand.ID + '?', r'(\w*RGA\w*)').group()
        log.debug('RGA response: %r', result)

        # success!  Stop the turbo
        self.assert_da_command(_turbo + turbo.DriverTestMixinSub.set_station_off,
                               turbo.DriverTestMixinSub.set_station_off)
        self.assert_da_command(_turbo + turbo.DriverTestMixinSub.set_pump_off,
                               turbo.DriverTestMixinSub.set_pump_off)

        # wait just a moment to allow the turbo to start spinning down...
        time.sleep(1)

        # put the MCU in standby
        self.assert_da_command(_mcu + mcu.InstrumentCommand.STANDBY, '(%s)' % mcu.Prompt.STANDBY, max_retries=60)

        self.assert_direct_access_stop_telnet()

    def test_poll(self):
        """
        Poll for a single sample
        """
        self.assert_enter_command_mode()
        self.assert_set_parameter(rga.Parameter.NF, 5)
        self.assert_set_parameter(rga.Parameter.MF, 50)
        self.assert_execute_resource(Capability.ACQUIRE_SAMPLE, timeout=100)
        # particles are verified in slave protocol qual tests... Here we just verify they are published
        self.assert_particle_async(mcu.DataParticleType.MCU_STATUS, Mock(), timeout=90)
        self.assert_particle_async(turbo.DataParticleType.TURBO_STATUS, Mock(), particle_count=20, timeout=500)
        self.assert_particle_async(rga.DataParticleType.RGA_STATUS, Mock(), timeout=600)
        self.assert_particle_async(rga.DataParticleType.RGA_SAMPLE, Mock(), particle_count=5, timeout=600)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, timeout=100)

    def test_autosample(self):
        """
        start and stop autosample and verify data particle
        """
        self.assert_enter_command_mode()
        self.assert_set_parameter(rga.Parameter.NF, 5)
        self.assert_set_parameter(rga.Parameter.MF, 50)
        self.assert_set_parameter(Parameter.SAMPLE_INTERVAL, 800)
        self.assert_execute_resource(Capability.START_AUTOSAMPLE, timeout=100)
        # particles are verified in slave protocol qual tests... Here we just verify they are published
        self.assert_particle_async(mcu.DataParticleType.MCU_STATUS, Mock(), timeout=90)
        self.assert_particle_async(turbo.DataParticleType.TURBO_STATUS, Mock(), particle_count=20, timeout=500)
        self.assert_particle_async(rga.DataParticleType.RGA_STATUS, Mock(), timeout=600)
        self.assert_particle_async(rga.DataParticleType.RGA_SAMPLE, Mock(), particle_count=5, timeout=600)
        # to verify we are actually autosampling, wait for another RGA_STATUS, which occurs once per sample cycle
        self.assert_particle_async(rga.DataParticleType.RGA_STATUS, Mock(), timeout=900)
        self.assert_execute_resource(Capability.STOP_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, timeout=900)

    def test_nafion(self):
        """
        Test the nafion regeneration command.  Nafion regen takes approx. 2 hours,
        should run for 2 minutes if U SETMINUTE01000 has been executed.
        """
        self.assert_enter_command_mode()
        self.assert_execute_resource(Capability.START_NAFION)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, timeout=600)

    def test_ion(self):
        """
        Test the ion chamber regeneration command.  Ion chamber regen takes approx. 2 hours,
        should run for 2 minutes if U SETMINUTE01000 has been executed.
        """
        self.assert_enter_command_mode()
        self.assert_execute_resource(Capability.START_ION)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, timeout=600)

    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        self.assert_enter_command_mode()

        parameters = Parameter.dict()
        parameters.update(turbo.Parameter.dict())
        parameters.update(rga.Parameter.dict())
        parameters.update(mcu.Parameter.dict())

        constraints = turbo.ParameterConstraints.dict()
        constraints.update(rga.ParameterConstraints.dict())

        for name, parameter in parameters.iteritems():
            if parameter == Parameter.ALL:
                continue
            if self._driver_parameters[parameter][self.READONLY]:
                with self.assertRaises(BadRequest):
                    self.assert_set_parameter(parameter, 'READONLY')
            else:
                value = massp_startup_config[DriverConfigKey.PARAMETERS].get(parameter)
                if value is not None:
                    if name in constraints:
                        _, minimum, maximum = constraints[name]
                        self.assert_set_parameter(parameter, minimum + 1)
                        with self.assertRaises(BadRequest):
                            self.assert_set_parameter(parameter, maximum + 1)
                    else:
                        self.assert_set_parameter(parameter, value + 1)

    def test_get_capabilities(self):
        """
        Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        ##################
        # Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [ProtocolEvent.START_AUTOSAMPLE,
                                                   ProtocolEvent.ACQUIRE_SAMPLE,
                                                   ProtocolEvent.START_ION,
                                                   ProtocolEvent.START_NAFION,
                                                   ProtocolEvent.CALIBRATE,
                                                   ProtocolEvent.POWEROFF,
                                                   ProtocolEvent.START_MANUAL],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_enter_command_mode()
        self.assert_capabilities(capabilities)

        ##################
        # Poll Mode
        ##################

        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: [],
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_execute_resource(Capability.ACQUIRE_SAMPLE)
        self.assert_state_change(ResourceAgentState.BUSY, ProtocolState.POLL, 20)
        self.assert_capabilities(capabilities)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 900)

        ##################
        # Autosample Mode
        ##################

        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.STREAMING),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [ProtocolEvent.STOP_AUTOSAMPLE,
                                                   ProtocolEvent.ACQUIRE_SAMPLE],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_execute_resource(Capability.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.STREAMING, ProtocolState.AUTOSAMPLE, 20)
        self.assert_capabilities(capabilities)
        self.assert_execute_resource(Capability.STOP_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 900)

        ##################
        # Calibrate Mode
        ##################

        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: [],
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_execute_resource(Capability.CALIBRATE)
        self.assert_state_change(ResourceAgentState.BUSY, ProtocolState.CALIBRATE, 20)
        self.assert_capabilities(capabilities)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 900)

        ##################
        # DA Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = self._common_da_resource_commands()

        self.assert_direct_access_start_telnet()
        self.assert_capabilities(capabilities)
        self.assert_direct_access_stop_telnet()

        #######################
        # Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.UNINITIALIZED)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)

    def test_direct_access_telnet_closed(self):
        """
        Test that we can properly handle the situation when a direct access
        session is launched, the telnet is closed, then direct access is stopped.
        Overridden to increase timeout due to long MCU reset time.
        """
        self.assert_enter_command_mode()
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)
        self.tcp_client.disconnect()
        self.assert_state_change(ResourceAgentState.COMMAND, DriverProtocolState.COMMAND, 120)
