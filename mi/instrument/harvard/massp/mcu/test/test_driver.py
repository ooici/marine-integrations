"""
@package mi.instrument.harvard.massp.mcu.test.test_driver
@file marine-integrations/mi/instrument/harvard/massp/mcu/driver.py
@author Peter Cable
@brief Test cases for mcu driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""
import time

from nose.plugins.attrib import attr
from mock import Mock
import ntplib
from mi.core.exceptions import SampleException, InstrumentCommandException
from mi.core.instrument.data_particle import RawDataParticle
from mi.core.instrument.port_agent_client import PortAgentPacket
from mi.core.log import get_logger
from mi.idk.unit_test import InstrumentDriverTestCase, ParameterTestConfigKey, AgentCapabilityType
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.core.instrument.instrument_driver import DriverConfigKey, ResourceAgentState, DriverProtocolState
from mi.core.instrument.chunker import StringChunker
from mi.instrument.harvard.massp.mcu.driver import InstrumentDriver
from mi.instrument.harvard.massp.mcu.driver import McuStatusParticleKey
from mi.instrument.harvard.massp.mcu.driver import DataParticleType
from mi.instrument.harvard.massp.mcu.driver import InstrumentCommand
from mi.instrument.harvard.massp.mcu.driver import ProtocolState
from mi.instrument.harvard.massp.mcu.driver import ProtocolEvent
from mi.instrument.harvard.massp.mcu.driver import Capability
from mi.instrument.harvard.massp.mcu.driver import Parameter
from mi.instrument.harvard.massp.mcu.driver import ParameterConstraint
from mi.instrument.harvard.massp.mcu.driver import Protocol
from mi.instrument.harvard.massp.mcu.driver import Prompt
from mi.instrument.harvard.massp.mcu.driver import NEWLINE


__author__ = 'Peter Cable'
__license__ = 'Apache 2.0'

log = get_logger()

mcu_startup_config = {DriverConfigKey.PARAMETERS: {
    Parameter.TELEGRAM_INTERVAL: 10000,
    Parameter.ONE_MINUTE: 1000,
    Parameter.SAMPLE_TIME: 10
}}

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.harvard.massp.mcu.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id='IN2N03',
    instrument_agent_name='harvard_massp_mcu',
    instrument_agent_packet_config=DataParticleType(),
    driver_startup_config=mcu_startup_config
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

TELEGRAM_1 = 'DATA,POW:0:1:2:3:4:5:6:7:8:9:10,' + \
             'PRE:1:2:3:4,' + \
             'INT:1:2:3:4:5:6:7:8:9:10,' + \
             'EXT:1:2:3,' + \
             'EXTST:1:2:3,' + \
             'POWST:0:1:2:3:4:5:6:7:8:9:10:11:12,' + \
             'SOLST:1:2:3:4:5:6,' + \
             'CAL:0:1:2:3:4:1:2:3:4,' + \
             'HEAT:0:1:2:3:4:5:6:7:8:9,' + \
             'ENDDATA'

TELEGRAM_2 = 'DATA,POW:4967:4983:1994:4978:4978:4973:1998:5124:2003:4994:6794,' + \
             'PRE:955:938:957:955,' + \
             'INT:50:35:17:20:20:21:20:20:20:20:20,' + \
             'EXT:2.00:0.00:-1.00,' + \
             'EXTST:1:0:0,' + \
             'POWST:0:0:0:0:1:0:0:0:0:0:0:0:0,' + \
             'SOLST:0:0:0:1:0:0,' + \
             'CAL:0:0:0:0:0:10:10:1:0,' + \
             'HEAT:0:0:0:20:0:-1:-1:-1:-1:-1,' + \
             'ENDDATA'

# missing all data
BAD_TELEGRAM_1 = 'DATA,ENDDATA'

# non-integer value
BAD_TELEGRAM_2 = 'DATA,POW:a:1:2:3:4:5:6:7:8:9:10,' + \
                 'PRE:1:2:3:4,' + \
                 'INT:1:2:3:4:5:6:7:8:9:10,' + \
                 'EXT:1:2:3,' + \
                 'EXTST:1:2:3,' + \
                 'POWST:0:1:2:3:4:5:6:7:8:9:10:11:12,' + \
                 'SOLST:1:2:3:4:5:6,' + \
                 'CAL:0:1:2:3:4:1:2:3:4,' + \
                 'HEAT:0:1:2:3:4:5:6:7:8:9,' + \
                 'ENDDATA'

# missing one value
BAD_TELEGRAM_3 = 'DATA,POW:0:1:2:3:4:5:6:7:8:9,' + \
                 'PRE:1:2:3:4,' + \
                 'INT:1:2:3:4:5:6:7:8:9:10,' + \
                 'EXT:1:2:3,' + \
                 'EXTST:1:2:3,' + \
                 'POWST:0:1:2:3:4:5:6:7:8:9:10:11:12,' + \
                 'SOLST:1:2:3:4:5:6,' + \
                 'CAL:0:1:2:3:4:1:2:3:4,' + \
                 'HEAT:0:1:2:3:4:5:6:7:8:9,' + \
                 'ENDDATA'


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

    def assert_sample_data_particle(self, data_particle):
        """
        Verify a particle is a know particle to this driver and verify the particle is correct
        @param data_particle: Data particle of unknown type produced by the driver
        """
        if isinstance(data_particle, RawDataParticle):
            self.assert_particle_raw(data_particle)
        else:
            self.fail("Unknown particle detected: %s" % data_particle)

    def assert_particle_exception(self, driver, sample_data):
        """
        Verify that we can send data through the port agent and the the correct particles are generated.

        Create a port agent packet, send it through got_data, then finally grab the data particle
        from the data particle queue and verify it using the passed in assert method.
        @param driver: instrument driver with mock port agent client
        @param sample_data: the byte string we want to send to the driver
        """
        try:
            # Push the data into the driver
            self._send_port_agent_packet(driver, sample_data)
            # uh oh, we shouldn't have reached this point
            self.fail('Failed to generate an exception when given bad data!')
        except SampleException, e:
            log.debug('Caught sample exception: %r', e)

    def _send_port_agent_packet(self, driver, data):
        """
        Send a port agent packet via got_data
        @param driver Instrument Driver instance
        @param data data to send
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
            my_response = self.responses.get(data.strip())
            log.debug("my_send: data: %r, my_response: %r", data, my_response)
            if my_response is not None:
                self._send_port_agent_packet(driver, my_response + NEWLINE)
                return len(my_response)
        return inner

    responses = {
        InstrumentCommand.START1: Prompt.OK,
        InstrumentCommand.START2: Prompt.OK,
        InstrumentCommand.SAMPLE + '10': Prompt.SAMPLE_START,
        InstrumentCommand.CAL: Prompt.OK,
        # instrument only sends one or the other (STANDBY or ONLINE) but for testing we can send both
        InstrumentCommand.STANDBY: Prompt.OK + NEWLINE + Prompt.STANDBY + NEWLINE + Prompt.ONLINE,
        InstrumentCommand.BEAT: Prompt.BEAT,
        InstrumentCommand.NAFREG: Prompt.OK,
        InstrumentCommand.IONREG: Prompt.OK,
        InstrumentCommand.SET_TELEGRAM_INTERVAL + '00010000': Prompt.OK,
        InstrumentCommand.SET_MINUTE + '01000': Prompt.SET_MINUTE,
        InstrumentCommand.SET_WATCHDOG: Prompt.OK,
    }

    _driver_parameters = {
        Parameter.TELEGRAM_INTERVAL: {TYPE: int, READONLY: False, DA: False, STARTUP: True, VALUE: 10000},
        Parameter.ONE_MINUTE: {TYPE: int, READONLY: True, DA: False, STARTUP: True, VALUE: 1000},
        Parameter.SAMPLE_TIME: {TYPE: int, READONLY: False, DA: False, STARTUP: True, VALUE: 10},
        Parameter.ERROR_REASON: {TYPE: str, READONLY: True, DA: False, STARTUP: False, VALUE: ''},
    }

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.START1: {STATES: [ProtocolState.COMMAND]},
        Capability.START2: {STATES: [ProtocolState.START1]},
        Capability.SAMPLE: {STATES: [ProtocolState.WAITING_RGA]},
        Capability.STANDBY: {STATES: [ProtocolState.WAITING_TURBO, ProtocolState.WAITING_RGA,
                                      ProtocolState.SAMPLE, ProtocolState.REGEN]},
        Capability.CLEAR: {STATES: [ProtocolState.ERROR]},
        Capability.IONREG: {STATES: [ProtocolState.COMMAND]},
        Capability.NAFREG: {STATES: [ProtocolState.COMMAND]},
        Capability.POWEROFF: {STATES: [ProtocolState.COMMAND]},
        Capability.CALIBRATE: {STATES: [ProtocolState.WAITING_RGA]},
    }

    _capabilities = {
        ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER',
                                'PROTOCOL_EVENT_ERROR'],
        ProtocolState.COMMAND: ['DRIVER_EVENT_GET',
                                'DRIVER_EVENT_SET',
                                'PROTOCOL_EVENT_ERROR',
                                'PROTOCOL_EVENT_POWEROFF',
                                'DRIVER_EVENT_START_DIRECT',
                                'PROTOCOL_EVENT_NAFREG',
                                'PROTOCOL_EVENT_IONREG',
                                'PROTOCOL_EVENT_START1'],
        ProtocolState.START1: ['PROTOCOL_EVENT_START1_COMPLETE',
                               'PROTOCOL_EVENT_STANDBY',
                               'PROTOCOL_EVENT_ERROR'],
        ProtocolState.START2: ['PROTOCOL_EVENT_START2_COMPLETE',
                               'PROTOCOL_EVENT_STANDBY',
                               'PROTOCOL_EVENT_ERROR'],
        ProtocolState.SAMPLE: ['PROTOCOL_EVENT_SAMPLE_COMPLETE',
                               'PROTOCOL_EVENT_STANDBY',
                               'PROTOCOL_EVENT_ERROR'],
        ProtocolState.CALIBRATE: ['PROTOCOL_EVENT_CALIBRATE_COMPLETE',
                                  'PROTOCOL_EVENT_STANDBY',
                                  'PROTOCOL_EVENT_ERROR'],
        ProtocolState.REGEN: ['PROTOCOL_EVENT_STANDBY', 'PROTOCOL_EVENT_ERROR'],
        ProtocolState.STOPPING: ['PROTOCOL_EVENT_STANDBY',
                                 'PROTOCOL_EVENT_ERROR'],
        ProtocolState.WAITING_RGA: ['PROTOCOL_EVENT_SAMPLE',
                                    'PROTOCOL_EVENT_STANDBY',
                                    'DRIVER_EVENT_CALIBRATE',
                                    'PROTOCOL_EVENT_ERROR'],
        ProtocolState.WAITING_TURBO: ['PROTOCOL_EVENT_START2',
                                      'PROTOCOL_EVENT_STANDBY',
                                      'PROTOCOL_EVENT_ERROR'],
        ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT'],
        ProtocolState.ERROR: ['PROTOCOL_EVENT_CLEAR',
                              'PROTOCOL_EVENT_STANDBY']
    }

    """
    'DATA,POW:4967:4983:1994:4978:4978:4973:1998:5124:2003:4994:6794,' + \
             'PRE:955:938:957:955,' + \
             'INT:50:35:17:20:20:21:20:20:20:20:20,' + \
             'EXT:2.00:0.00:-1.00,' + \
             'EXTST:1:0:0,' + \
             'POWST:0:0:0:0:1:0:0:0:0:0:0:0:0,' + \
             'SOLST:0:0:0:1:0:0,' + \
             'CAL:0:0:0:0:0:10:10:1:0,' + \
             'HEAT:0:0:0:20:0:-1:-1:-1:-1:-1,' + \
             'ENDDATA'
    """
    _status_parameters = {
        McuStatusParticleKey.RGA_CURRENT: {TYPE: int, VALUE: 4967, REQUIRED: True},
        McuStatusParticleKey.TURBO_CURRENT: {TYPE: int, VALUE: 4983, REQUIRED: True},
        McuStatusParticleKey.HEATER_CURRENT: {TYPE: int, VALUE: 1994, REQUIRED: True},
        McuStatusParticleKey.ROUGHING_CURRENT: {TYPE: int, VALUE: 4978, REQUIRED: True},
        McuStatusParticleKey.FAN_CURRENT: {TYPE: int, VALUE: 4978, REQUIRED: True},
        McuStatusParticleKey.SBE_CURRENT: {TYPE: int, VALUE: 4973, REQUIRED: True},
        McuStatusParticleKey.CONVERTER_24V_MAIN: {TYPE: int, VALUE: 1998, REQUIRED: True},
        McuStatusParticleKey.CONVERTER_12V_MAIN: {TYPE: int, VALUE: 5124, REQUIRED: True},
        McuStatusParticleKey.CONVERTER_24V_SEC: {TYPE: int, VALUE: 2003, REQUIRED: True},
        McuStatusParticleKey.CONVERTER_12V_SEC: {TYPE: int, VALUE: 4994, REQUIRED: True},
        McuStatusParticleKey.VALVE_CURRENT: {TYPE: int, VALUE: 6794, REQUIRED: True},
        McuStatusParticleKey.PRESSURE_P1: {TYPE: int, VALUE: 955, REQUIRED: True},
        McuStatusParticleKey.PRESSURE_P2: {TYPE: int, VALUE: 938, REQUIRED: True},
        McuStatusParticleKey.PRESSURE_P3: {TYPE: int, VALUE: 957, REQUIRED: True},
        McuStatusParticleKey.PRESSURE_P4: {TYPE: int, VALUE: 955, REQUIRED: True},
        McuStatusParticleKey.HOUSING_PRESSURE: {TYPE: int, VALUE: 50, REQUIRED: True},
        McuStatusParticleKey.HOUSING_HUMIDITY: {TYPE: int, VALUE: 35, REQUIRED: True},
        McuStatusParticleKey.TEMP_MAIN_CONTROL: {TYPE: int, VALUE: 17, REQUIRED: True},
        McuStatusParticleKey.TEMP_MAIN_ROUGH: {TYPE: int, VALUE: 20, REQUIRED: True},
        McuStatusParticleKey.TEMP_SEC_ROUGH: {TYPE: int, VALUE: 20, REQUIRED: True},
        McuStatusParticleKey.TEMP_MAIN_24V: {TYPE: int, VALUE: 21, REQUIRED: True},
        McuStatusParticleKey.TEMP_SEC_24V: {TYPE: int, VALUE: 20, REQUIRED: True},
        McuStatusParticleKey.TEMP_ANALYZER: {TYPE: int, VALUE: 20, REQUIRED: True},
        McuStatusParticleKey.TEMP_NAFION: {TYPE: int, VALUE: 20, REQUIRED: True},
        McuStatusParticleKey.TEMP_ION: {TYPE: int, VALUE: 20, REQUIRED: True},
        McuStatusParticleKey.PH_METER: {TYPE: int, VALUE: 2, REQUIRED: True},
        McuStatusParticleKey.INLET_TEMP: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.PH_STATUS: {TYPE: int, VALUE: 1, REQUIRED: True},
        McuStatusParticleKey.INLET_TEMP_STATUS: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_TURBO: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_RGA: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_MAIN_ROUGH: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_SEC_ROUGH: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_FAN1: {TYPE: int, VALUE: 1, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_FAN2: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_FAN3: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_FAN4: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_AUX2: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_PH: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_PUMP: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_HEATERS: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.POWER_RELAY_AUX1: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.SAMPLE_VALVE1: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.SAMPLE_VALVE2: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.SAMPLE_VALVE3: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.SAMPLE_VALVE4: {TYPE: int, VALUE: 1, REQUIRED: True},
        McuStatusParticleKey.GROUND_RELAY_STATUS: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.EXTERNAL_VALVE1_STATUS: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.EXTERNAL_VALVE2_STATUS: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.EXTERNAL_VALVE3_STATUS: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.EXTERNAL_VALVE4_STATUS: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.CAL_BAG1_MINUTES: {TYPE: int, VALUE: 10, REQUIRED: True},
        McuStatusParticleKey.CAL_BAG2_MINUTES: {TYPE: int, VALUE: 10, REQUIRED: True},
        McuStatusParticleKey.CAL_BAG3_MINUTES: {TYPE: int, VALUE: 1, REQUIRED: True},
        McuStatusParticleKey.NAFION_HEATER_STATUS: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.NAFION_HEATER1_POWER: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.NAFION_HEATER2_POWER: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.NAFION_CORE_TEMP: {TYPE: int, VALUE: 20, REQUIRED: True},
        McuStatusParticleKey.NAFION_ELAPSED_TIME: {TYPE: int, VALUE: 0, REQUIRED: True},
        McuStatusParticleKey.ION_CHAMBER_STATUS: {TYPE: int, VALUE: -1, REQUIRED: True},
        McuStatusParticleKey.ION_CHAMBER_HEATER1_STATUS: {TYPE: int, VALUE: -1, REQUIRED: True},
        McuStatusParticleKey.ION_CHAMBER_HEATER2_STATUS: {TYPE: int, VALUE: -1, REQUIRED: True},
    }

    def assert_mcu_status_particle(self, particle, verify_values=False):
        self.assert_data_particle_keys(McuStatusParticleKey, self._status_parameters)
        self.assert_data_particle_header(particle, DataParticleType.MCU_STATUS)
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
        @param initial_protocol_state Desired initial protocol state
        @returns driver
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, initial_protocol_state)
        log.debug('Adding Mock side effect to connection.send')
        driver._connection.send.side_effect = self.my_send(driver)
        driver._protocol.set_init_params(mcu_startup_config)
        driver._protocol._init_params()
        return driver

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilities
        """
        self.assert_enum_has_no_duplicates(DataParticleType)
        self.assert_enum_has_no_duplicates(ProtocolState)
        self.assert_enum_has_no_duplicates(ProtocolEvent)
        self.assert_enum_has_no_duplicates(Parameter)
        self.assert_enum_has_no_duplicates(InstrumentCommand)
        self.assert_enum_has_no_duplicates(Prompt)

        # Test capabilities for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability)
        self.assert_enum_complete(Capability, ProtocolEvent)

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, self._capabilities)

    def test_chunker(self):
        """
        Test the chunker
        """
        chunker = StringChunker(Protocol.sieve_function)
        chunks = [TELEGRAM_1]

        for chunk in chunks:
            self.assert_chunker_sample(chunker, chunk + NEWLINE)
            self.assert_chunker_fragmented_sample(chunker, chunk + NEWLINE)
            self.assert_chunker_sample_with_noise(chunker, chunk + NEWLINE)
            self.assert_chunker_combined_sample(chunker, chunk + NEWLINE)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        driver = self.test_connect()
        test_data = [
            (TELEGRAM_1, True, False),
            (TELEGRAM_2, True, True),
            (BAD_TELEGRAM_1, False, False),
            (BAD_TELEGRAM_2, False, False),
            (BAD_TELEGRAM_3, False, False),
        ]
        for sample, is_valid, verify in test_data:
            if is_valid:
                self.assert_particle_published(driver, sample + NEWLINE, self.assert_mcu_status_particle, verify)
            else:
                self.assert_particle_exception(driver, sample + NEWLINE)

    def test_sample_sequence(self):
        """
        Test the MCU ASAMPLE sequence handling
        """
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START1)
        self._send_port_agent_packet(driver, Prompt.START1 + NEWLINE)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START2)
        self._send_port_agent_packet(driver, Prompt.START2 + NEWLINE)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.SAMPLE)
        self._send_port_agent_packet(driver, Prompt.SAMPLE_FINISHED + NEWLINE)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.STANDBY)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

    def test_cal_sequence(self):
        """
        Test the MCU ACAL9 sequence handling
        """
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START1)
        self._send_port_agent_packet(driver, Prompt.START1 + NEWLINE)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START2)
        self._send_port_agent_packet(driver, Prompt.START2 + NEWLINE)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.CALIBRATE)
        self._send_port_agent_packet(driver, Prompt.CAL_FINISHED + NEWLINE)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.STANDBY)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        protocol = Protocol(Prompt, NEWLINE, Mock())
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

    def test_regen(self):
        """
        Verify we can start/stop the regen states
        """
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.NAFREG)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.REGEN)
        self._send_port_agent_packet(driver, Prompt.NAFREG_FINISHED + NEWLINE)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

        driver._protocol._protocol_fsm.on_event(ProtocolEvent.IONREG)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.REGEN)
        self._send_port_agent_packet(driver, Prompt.IONREG_FINISHED + NEWLINE)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

    def test_regen_stop(self):
        """
        Verify we can abort the regen states
        """
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.NAFREG)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.REGEN)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.STANDBY)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

        driver._protocol._protocol_fsm.on_event(ProtocolEvent.IONREG)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.REGEN)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.STANDBY)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)


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

    def test_connect(self):
        """
        Stand up the driver, transition to COMMAND
        """
        self.assert_initialize_driver()

    def test_get(self):
        self.assert_initialize_driver()
        for param in self._driver_parameters:
            self.assert_get(param, self._driver_parameters[param][self.VALUE])

    def test_set_and_bad_command(self):
        """
        Test setting of parameters, including exceptions for bad parameters/values.
        Test exception on receipt of bad command.
        Combined due to long startup time.
        """
        self.assert_initialize_driver()

        constraints = ParameterConstraint.dict()
        parameters = Parameter.dict()
        for key in constraints:
            _type, minimum, maximum = constraints[key]
            param = parameters[key]
            if not self._driver_parameters[param][self.READONLY]:
                self.assert_set(param, maximum)
                self.assert_set_exception(param, maximum + 1)
            else:
                self.assert_set_exception(param, maximum)

        self.assert_set_exception('BOGUS', 'CHEESE')
        self.assert_driver_command_exception('BAD_COMMAND', exception_class=InstrumentCommandException)

    def test_start1_and_data_particle(self):
        """
        Test sending the START1 command and data particle generation
        """
        self.assert_initialize_driver()
        self.assert_driver_command(Capability.START1)
        self.assert_state_change(ProtocolState.WAITING_TURBO, 60)
        self.assert_async_particle_generation(DataParticleType.MCU_STATUS, self.assert_mcu_status_particle, timeout=60)
        self.assert_driver_command(Capability.STANDBY)
        self.assert_driver_command(Capability.POWEROFF)

    def test_regen(self):
        """
        Test the ion chamber and nafion regen commands
        """
        self.assert_initialize_driver()
        self.assert_driver_command(Capability.IONREG)
        self.assert_state_change(ProtocolState.REGEN, 5)
        self.assert_driver_command(Capability.STANDBY)
        self.assert_state_change(ProtocolState.COMMAND, 20)

        self.assert_driver_command(Capability.NAFREG)
        self.assert_state_change(ProtocolState.REGEN, 5)
        self.assert_driver_command(Capability.STANDBY)
        self.assert_state_change(ProtocolState.COMMAND, 20)


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

    def test_data_particle(self):
        """
        Test data particle generation
        """
        self.assert_enter_command_mode()
        self.assert_particle_async(DataParticleType.MCU_STATUS, self.assert_mcu_status_particle, timeout=90)

    def test_direct_access_telnet_mode(self):
        """
        This test manually tests that the Instrument Driver properly supports
        direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet(session_timeout=180)
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data(InstrumentCommand.BEAT + NEWLINE)
        self.assertTrue(self.tcp_client.expect(Prompt.BEAT))
        self.tcp_client.send_data(InstrumentCommand.START1 + NEWLINE)
        self.assertTrue(self.tcp_client.expect(Prompt.OK))
        self.assertTrue(self.tcp_client.expect(Prompt.START1, max_retries=90))
        self.tcp_client.send_data(InstrumentCommand.STANDBY + NEWLINE)
        self.assertTrue(self.tcp_client.expect(Prompt.OK))

        self.assert_direct_access_stop_telnet()

    def test_discover(self):
        """
        Overridden, this driver does not have autosample
        """
        # Verify the agent is in command mode
        self.assert_enter_command_mode()

        # Now reset and try to discover.  This will stop the driver which holds the current
        # instrument state.
        self.assert_reset()
        self.assert_discover(ResourceAgentState.COMMAND)

    def test_reset(self):
        """
        Verify the agent can be reset
        Overridden, this driver does not have autosample.
        """
        self.assert_enter_command_mode()
        self.assert_reset()

        self.assert_enter_command_mode()
        self.assert_direct_access_start_telnet(session_timeout=180)
        self.assert_state_change(ResourceAgentState.DIRECT_ACCESS, DriverProtocolState.DIRECT_ACCESS, 30)
        self.assert_reset()

    def test_get_capabilities(self):
        """
        Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.

        We will only test command, direct_access and unknown, as we cannot reach all states with just the
        MCU driver.
        """
        self.assert_enter_command_mode()

        ##################
        # Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                ProtocolEvent.START1,
                ProtocolEvent.NAFREG,
                ProtocolEvent.IONREG,
                ProtocolEvent.POWEROFF,
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

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
        OVERRIDDEN to extend timeout period to return to command.
        """
        self.assert_enter_command_mode()
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)
        self.tcp_client.disconnect()
        self.assert_state_change(ResourceAgentState.COMMAND, DriverProtocolState.COMMAND, 90)
