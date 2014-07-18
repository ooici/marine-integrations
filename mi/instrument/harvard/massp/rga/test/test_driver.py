"""
@package mi.instrument.harvard.massp.rga.test.test_driver
@file marine-integrations/mi/instrument/harvard/massp/rga/driver.py
@author Peter Cable
@brief Test cases for rga driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Peter Cable'
__license__ = 'Apache 2.0'

import json
import struct
import time
import unittest

import ntplib
from nose.plugins.attrib import attr
from mock import Mock, call
from mi.idk.unit_test import InstrumentDriverTestCase, ParameterTestConfigKey
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.instrument.data_particle import RawDataParticle, CommonDataParticleType
from mi.core.instrument.instrument_driver import DriverConfigKey, ResourceAgentState
from mi.core.instrument.port_agent_client import PortAgentPacket
from mi.instrument.harvard.massp.rga.driver import InstrumentDriver
from mi.instrument.harvard.massp.rga.driver import RGAStatusParticleKey
from mi.instrument.harvard.massp.rga.driver import RGASampleParticleKey
from mi.instrument.harvard.massp.rga.driver import ParameterConstraints
from mi.instrument.harvard.massp.rga.driver import DataParticleType
from mi.instrument.harvard.massp.rga.driver import InstrumentCommand
from mi.instrument.harvard.massp.rga.driver import ProtocolState
from mi.instrument.harvard.massp.rga.driver import ProtocolEvent
from mi.instrument.harvard.massp.rga.driver import Capability
from mi.instrument.harvard.massp.rga.driver import Parameter
from mi.instrument.harvard.massp.rga.driver import Protocol
from mi.instrument.harvard.massp.rga.driver import Prompt
from mi.instrument.harvard.massp.rga.driver import NEWLINE
from mi.core.log import get_logger


log = get_logger()

rga_startup_config = {
    DriverConfigKey.PARAMETERS: {
        Parameter.EE: 70,
        Parameter.IE: 1,
        Parameter.VF: 90,
        Parameter.NF: 3,
        Parameter.SA: 10,
        Parameter.MI: 1,
        Parameter.MF: 100,
        Parameter.FL: 1.0,
        Parameter.HV: 0,
    }
}


###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.harvard.massp.rga.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='YAQ3KY',
    instrument_agent_name='harvard_massp_rga',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config=rga_startup_config
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

###
#   Driver constant definitions
###

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

    def assert_sample_data_particle(self, data_particle):
        """
        Verify a particle is a know particle to this driver and verify the particle is
        correct
        @param data_particle: Data particle of unknown type produced by the driver
        """
        if isinstance(data_particle, RawDataParticle):
            self.assert_particle_raw(data_particle)
        else:
            self.fail("Unknown Particle Detected: %s" % data_particle)

    responses = {
        'IN0': 0,
        'EE70': 0,
        'EE?': 70,
        'IE1': 0,
        'IE?': 1,
        'VF90': 0,
        'VF?': 90,
        'NF?': 3,
        'SA?': 10,
        'MI?': 1,
        'MF?': 100,
        'FL1.0': 0,
        'FL?': 0.9976,
        'AP?': 251,
        'ID?': 'FAKEID',
        'SC1': '\xba\xdd\xca\xfe' * 252,
        'ER?': 0,
        'HV?': 0,
        'HV0': 0,
    }

    sample_data = list(struct.unpack('<252i', responses['SC1']))

    _sample_parameters = {
        RGASampleParticleKey.SCAN_DATA: {TYPE: list, VALUE: sample_data, REQUIRED: True},
    }

    _status_parameters = {
        RGAStatusParticleKey.ID: {TYPE: unicode, VALUE: responses['ID?'], REQUIRED: True},
        RGAStatusParticleKey.EE: {TYPE: int, VALUE: responses['EE?'], REQUIRED: True},
        RGAStatusParticleKey.IE: {TYPE: int, VALUE: responses['IE?'], REQUIRED: True},
        RGAStatusParticleKey.VF: {TYPE: int, VALUE: responses['VF?'], REQUIRED: True},
        RGAStatusParticleKey.NF: {TYPE: int, VALUE: responses['NF?'], REQUIRED: True},
        RGAStatusParticleKey.ER: {TYPE: int, VALUE: responses['ER?'], REQUIRED: True},
        RGAStatusParticleKey.SA: {TYPE: int, VALUE: responses['SA?'], REQUIRED: True},
        RGAStatusParticleKey.MI: {TYPE: int, VALUE: responses['MI?'], REQUIRED: True},
        RGAStatusParticleKey.MF: {TYPE: int, VALUE: responses['MF?'], REQUIRED: True},
        RGAStatusParticleKey.AP: {TYPE: int, VALUE: responses['AP?'], REQUIRED: True},
        RGAStatusParticleKey.HV: {TYPE: int, VALUE: responses['HV?'], REQUIRED: True},
        RGAStatusParticleKey.FL: {TYPE: float, VALUE: 1.0, REQUIRED: True},
        RGAStatusParticleKey.FL_ACTUAL: {TYPE: float, VALUE: responses['FL?'], REQUIRED: True},
    }

    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.ID: {TYPE: str, READONLY: True, DA: False, STARTUP: False},
        Parameter.AP: {TYPE: int, READONLY: True, DA: False, STARTUP: False},
        Parameter.ER: {TYPE: int, READONLY: True, DA: False, STARTUP: False},
        Parameter.EE: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.IE: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.VF: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.NF: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.SA: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.MI: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.MF: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.HV: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.FL: {TYPE: float, READONLY: False, DA: False, STARTUP: True},
        Parameter.FL_ACTUAL: {TYPE: float, READONLY: True, DA: False, STARTUP: True},
        Parameter.ERROR_REASON: {TYPE: str, READONLY: True, DA: False, STARTUP: False},
    }

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.START_SCAN: {STATES: [ProtocolState.COMMAND]},
        Capability.STOP_SCAN: {STATES: [ProtocolState.SCAN]},
        Capability.CLEAR: {STATES: [ProtocolState.ERROR]},
    }

    _capabilities = {
        ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
        ProtocolState.COMMAND: ['DRIVER_EVENT_GET',
                                'DRIVER_EVENT_SET',
                                'DRIVER_EVENT_START_DIRECT',
                                'PROTOCOL_EVENT_START_SCAN'],
        ProtocolState.SCAN: ['PROTOCOL_EVENT_TAKE_SCAN',
                             'PROTOCOL_EVENT_STOP_SCAN',
                             'PROTOCOL_EVENT_TIMEOUT',
                             'PROTOCOL_EVENT_ERROR'],
        ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT'],
        ProtocolState.ERROR: ['PROTOCOL_EVENT_CLEAR', 'DRIVER_EVENT_GET']
    }

    def _send_port_agent_packet(self, driver, data):
        """
        Send the supplied data to the driver in a port agent packet
        @param driver: instrument driver instance
        @param data: data to be sent
        """
        ts = ntplib.system_to_ntp_time(time.time())
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(data)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()

        # Push the response into the driver
        driver._protocol.got_data(port_agent_packet)

    def my_send(self, driver):
        """
        Side effect function generator - will send responses based on input
        @param driver Instrument driver instance
        @returns side effect function
        """
        def inner(data):
            """
            Inner function for side effect generator
            @param data Data to send
            @returns length of response
            """
            data = data.replace(NEWLINE, '')
            log.trace('my_send data: %r', data)
            my_response = str(self.responses.get(data))
            if my_response is not None:
                log.trace("my_send: data: %r, my_response: %r", data, my_response)
                # scans repeat over and over, sleep between them to prevent overloading cpu
                if data == 'SC1':
                    time.sleep(0.9)
                self._send_port_agent_packet(driver, my_response + '\n' + NEWLINE)
                return len(my_response)

        return inner

    def assert_rga_sample_particle(self, particle, verify_values=False):
        log.debug('assert_rga_sample_particle: %r', particle)
        self.assert_data_particle_keys(RGASampleParticleKey, self._sample_parameters)
        self.assert_data_particle_header(particle, DataParticleType.RGA_SAMPLE)
        self.assert_data_particle_parameters(particle, self._sample_parameters, verify_values)

    def assert_rga_status_particle(self, particle, verify_values=False):
        log.debug('assert_rga_status_particle: %r', particle)
        self.assert_data_particle_keys(RGAStatusParticleKey, self._status_parameters)
        self.assert_data_particle_header(particle, DataParticleType.RGA_STATUS)
        self.assert_data_particle_parameters(particle, self._status_parameters, verify_values)


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

    def test_connect(self, initial_protocol_state=ProtocolState.COMMAND):
        """
        Verify driver can transition to the COMMAND state
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, initial_protocol_state)
        driver._connection.send.side_effect = self.my_send(driver)
        driver._protocol.set_init_params(rga_startup_config)
        driver._protocol._init_params()
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
        self.assert_enum_has_no_duplicates(InstrumentCommand())

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

    def test_start_scan(self):
        """
        Send a start scan event to the driver.
        Use the side_effect on send from the mock port agent to simulate instrument responses.
        This checks the chunker and particle generation, since the chunker and particles are
        dynamic based on instrument parameters.
        """
        driver = self.test_connect()
        self.clear_data_particle_queue()
        driver._protocol._protocol_fsm.on_event(Capability.START_SCAN)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.SCAN)

        particles = []

        # loop, because the monkey patched time doesn't reliably sleep long enough...
        now = time.time()
        while time.time() < (now+5):
            time.sleep(1)

        for p in self._data_particle_received:
            particle_dict = json.loads(p)
            stream_type = particle_dict.get('stream_name')
            self.assertIsNotNone(stream_type)
            if stream_type != CommonDataParticleType.RAW:
                particles.append((p, stream_type))

        log.debug("Non raw particles: %s ", particles)
        self.assertGreaterEqual(len(particles), 1)

        for p, stream_name in particles:
            if stream_name == DataParticleType.RGA_STATUS:
                self.assert_rga_status_particle(p, True)
            else:
                self.assert_rga_sample_particle(p, True)

    def test_sample_missing_data(self):
        """
        Send a start scan event to the driver, but don't return enough data.  Verify that no
        sample particle is produced but the driver starts another scan.
        """
        orig_scan = self.responses['SC1']
        self.responses['SC1'] = 'this is a bad scan, man!'
        driver = self.test_connect()

        # side effect for our Mocked on_event
        def my_on_event(event):
            log.debug('my_on_event: event: %r', event)
            driver._protocol._protocol_fsm.on_event_actual(event)

        # swap out on_event with a Mock object now
        on_event_mock = Mock()
        on_event_mock.side_effect = my_on_event
        driver._protocol._protocol_fsm.on_event_actual = driver._protocol._protocol_fsm.on_event
        driver._protocol._protocol_fsm.on_event = on_event_mock
        driver._protocol._protocol_fsm.on_event(Capability.START_SCAN)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.SCAN)

        # clear the particle queue to remove the status particle
        self.clear_data_particle_queue()

        # sleep a bit
        time.sleep(15)

        # check for the correct calls
        on_event_mock.assert_has_calls([call(Capability.START_SCAN),
                                        call(Capability.TAKE_SCAN),
                                        call(ProtocolEvent.TIMEOUT)])
        self.responses['SC1'] = orig_scan

        # check there are no particles
        self.assertEqual(len(self._data_particle_received), 0)

    def test_error_byte(self):
        """
        Respond with an error and verify the FSM transitions to an error state.
        """
        driver = self.test_connect()
        # set up responses to return an error when the filament is enabled
        self.responses['FL1.0'] = 1
        try:
            driver._protocol._protocol_fsm.on_event(Capability.START_SCAN)
            self.assertTrue(False, msg='Failed to raise an exception when the error byte was set')
        except InstrumentStateException:
            # we threw an exception as expected.
            pass
        finally:
            # restore responses so other tests don't fail!
            self.responses['FL1.0'] = 0
        # make sure we moved to the ERROR state
        time.sleep(.1)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.ERROR)
        # clear the error, assert we moved back to COMMAND
        driver._protocol._protocol_fsm.on_event(Capability.CLEAR)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
        protocol = Protocol(Prompt, NEWLINE, mock_callback)
        driver_capabilities = Capability.list()
        test_capabilities = Capability.list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, DriverTestMixinSub):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_take_scan(self):
        """
        Start a scan and verify status and sample particles are generated.
        """
        self.assert_initialize_driver()
        self.assert_driver_command(Capability.START_SCAN)
        self.assert_state_change(ProtocolState.SCAN, 5)
        self.assert_async_particle_generation(DataParticleType.RGA_STATUS, self.assert_rga_status_particle)
        self.assert_async_particle_generation(DataParticleType.RGA_SAMPLE, self.assert_rga_sample_particle, 2, 600)
        self.assert_driver_command(Capability.STOP_SCAN)

    @unittest.skip("This takes a very long time...  Don't run it unless you mean it!")
    def test_scan_parameters(self):
        """
        Step through a sequence of configuration parameters to test scan timing.  Data is in confluence.
        """
        self.assert_initialize_driver()
        self.assert_set(Parameter.MI, 5, no_get=True)
        for mf in range(10, 100, 5):
            self.assert_set(Parameter.MF, mf, no_get=True)
            for nf in range(1, 8):
                self.clear_events()
                self.assert_set(Parameter.NF, nf, no_get=True)
                self.assert_driver_command(Capability.START_SCAN)
                self.assert_state_change(ProtocolState.SCAN, 5)
                self.assert_async_particle_generation(DataParticleType.RGA_STATUS, Mock())
                self.assert_async_particle_generation(DataParticleType.RGA_SAMPLE, Mock(), 2, 900)
                self.assert_driver_command(Capability.STOP_SCAN)
                self.assert_state_change(ProtocolState.COMMAND, 5)

    # while this is an integration test, it can be run without access to the instrument
    def test_get_parameters(self):
        """
        Verify we can get all parameters
        """
        self.assert_initialize_driver()
        startup_params = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
        for key, value in startup_params.items():
            self.assert_get(key, value)

    # while this is an integration test, it can be run without access to the instrument
    def test_set_parameters(self):
        """
        Verify we can set all parameters
        """
        self.assert_initialize_driver()
        constraints = ParameterConstraints.dict()
        parameters = Parameter.reverse_dict()
        startup_params = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
        for key, value in startup_params.iteritems():
            if key in parameters and parameters[key] in constraints:
                _, minimum, maximum = constraints[parameters[key]]
                self.assert_set(key, maximum-1)
            else:
                self.assert_set(key, value + 1)

        self.assert_set_bulk(startup_params)

    # while this is an integration test, it can be run without access to the instrument
    def test_out_of_range(self):
        """
        Verify out of range values raise exceptions
        """
        self.assert_initialize_driver()
        constraints = ParameterConstraints.dict()
        parameters = Parameter.dict()
        log.debug(constraints)
        for key in constraints:
            _, minimum, maximum = constraints[key]
            parameter = parameters[key]
            self.assert_set_exception(parameter, minimum - 1)
            self.assert_set_exception(parameter, maximum + 1)
            self.assert_set_exception(parameter, "strings aren't valid here!")

    def test_set_bogus_parameter(self):
        """
        Verify bogus parameters raise exceptions
        """
        self.assert_initialize_driver()
        self.assert_set_exception('BOGUS', 'CHEESE')

    def test_state_transitions(self):
        """
        Verify state transitions
        """
        self.assert_initialize_driver()
        self.assert_driver_command(Capability.START_SCAN)
        self.assert_state_change(ProtocolState.SCAN, 5)
        self.assert_driver_command(Capability.STOP_SCAN)
        self.assert_state_change(ProtocolState.COMMAND, 5)
        # verify the filament is off
        self.assert_get(Parameter.FL_ACTUAL, 0.0)

    def test_bad_command(self):
        """
        Verify bad commands raise exceptions
        """
        self.assert_initialize_driver()
        self.assert_driver_command_exception('BAD_COMMAND', exception_class=InstrumentCommandException)

    def test_incomplete_config(self):
        """
        Break our startup config, then verify the driver raises an exception
        """
        # grab the old config
        startup_params = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
        old_value = startup_params[Parameter.EE]
        try:
            # delete a required parameter
            del (startup_params[Parameter.EE])
            # re-init to take our broken config
            self.init_driver_process_client()
            self.assert_initialize_driver()
            # request start scan
            self.assert_driver_command(Capability.START_SCAN)
            self.assertTrue(False, msg='Failed to raise exception on missing parameter')
        except Exception as e:
            self.assertTrue(self._driver_exception_match(e, InstrumentProtocolException))
        finally:
            startup_params[Parameter.EE] = old_value


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase, DriverTestMixinSub):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_direct_access_telnet_mode(self):
        """
        This test manually tests that the Instrument Driver properly supports
        direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data(InstrumentCommand.ID + '?' + NEWLINE)
        self.assertTrue(self.tcp_client.expect('SRSRGA200'))

        self.assert_direct_access_stop_telnet()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 5)

    def test_poll(self):
        """
        A scan is the closest thing we have to a poll here...
        """
        self.assert_enter_command_mode()
        self.assert_particle_polled(Capability.START_SCAN,
                                    self.assert_rga_status_particle,
                                    DataParticleType.RGA_STATUS,
                                    timeout=30)
        self.assert_particle_async(DataParticleType.RGA_SAMPLE, self.assert_rga_sample_particle, timeout=100)
        self.assert_execute_resource(Capability.STOP_SCAN)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 5)

    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        self.assert_enter_command_mode()
        constraints = ParameterConstraints.dict()
        parameters = Parameter.reverse_dict()
        startup_params = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
        for key, value in startup_params.items():
            self.assert_get_parameter(key, value)
            if key in parameters and parameters[key] in constraints:
                _, minimum, maximum = constraints[parameters[key]]
                self.assert_set_parameter(key, maximum-1)
            else:
                self.assert_set_parameter(key, value + 1)

    def test_reset(self):
        """
        Verify the agent can be reset
        Overridden, driver does not have autosample
        """
        self.assert_enter_command_mode()
        self.assert_reset()

    def test_discover(self):
        """
        Overridden, driver does not have autosample
        """
        # Verify the agent is in command mode
        self.assert_enter_command_mode()

        # Now reset and try to discover.  This will stop the driver which holds the current
        # instrument state.
        self.assert_reset()
        self.assert_discover(ResourceAgentState.COMMAND)
