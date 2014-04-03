"""
@package mi.instrument.noaa.nano.ooicore.test.test_driver
@file marine-integrations/mi/instrument/noaa/nano/ooicore/driver.py
@author David Everett
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr
from mock import Mock, call

from mi.core.log import get_logger


log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType

from mi.core.instrument.port_agent_client import PortAgentPacket

from mi.core.instrument.chunker import StringChunker

from mi.instrument.noaa.botpt.nano.driver import InstrumentDriver
from mi.instrument.noaa.botpt.nano.driver import DataParticleType
from mi.instrument.noaa.botpt.nano.driver import NANODataParticleKey
from mi.instrument.noaa.botpt.nano.driver import NANODataParticle
from mi.instrument.noaa.botpt.nano.driver import InstrumentCommand
from mi.instrument.noaa.botpt.nano.driver import ProtocolState
from mi.instrument.noaa.botpt.nano.driver import ProtocolEvent
from mi.instrument.noaa.botpt.nano.driver import Capability
from mi.instrument.noaa.botpt.nano.driver import Parameter
from mi.instrument.noaa.botpt.nano.driver import Protocol
from mi.instrument.noaa.botpt.nano.driver import Prompt
from mi.instrument.noaa.botpt.nano.driver import NEWLINE

from mi.core.exceptions import SampleException
from pyon.agent.agent import ResourceAgentState

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.noaa.botpt.nano.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='1D644T',
    instrument_agent_name='noaa_nano_ooicore',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config={}
)

GO_ACTIVE_TIMEOUT = 180

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

INVALID_SAMPLE = "This is an invalid sample; it had better cause an exception." + NEWLINE
VALID_SAMPLE_01 = "NANO,V,2013/08/22 22:48:36.013,13.888533,26.147947328" + NEWLINE
VALID_SAMPLE_02 = "NANO,P,2013/08/22 23:13:36.000,13.884067,26.172926006" + NEWLINE

BOTPT_FIREHOSE_01 = "NANO,V,2013/08/22 22:48:36.013,13.888533,26.147947328" + NEWLINE
BOTPT_FIREHOSE_01 += "LILY,2013/05/16 17:03:22,-202.490,-330.000,149.88, 25.72,11.88,N9656" + NEWLINE
BOTPT_FIREHOSE_01 += "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE
#BOTPT_FIREHOSE_01  += "NANO,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642" + NEWLINE
#BOTPT_FIREHOSE_01  += "NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840" + NEWLINE
BOTPT_FIREHOSE_01 += "LILY,2013/05/16 17:03:22,-202.490,-330.000,149.88, 25.72,11.88,N9656" + NEWLINE
BOTPT_FIREHOSE_01 += "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE

SET_TIME_RESPONSE = "NANO,*0001GR=08/28/13 18:15:15" + NEWLINE

DUMP_STATUS = \
    "NANO,*--------------------------------------------------------------" + NEWLINE + \
    "NANO,*PAROSCIENTIFIC SMT SYSTEM INFORMATION" + NEWLINE + \
    "NANO,*Model Number: 42.4K-265" + NEWLINE + \
    "NANO,*Serial Number: 120785" + NEWLINE + \
    "NANO,*Firmware Revision: R5.20" + NEWLINE + \
    "NANO,*Firmware Release Date: 03-25-13" + NEWLINE + \
    "NANO,*PPS status: V : PPS signal NOT detected." + NEWLINE + \
    "NANO,*--------------------------------------------------------------" + NEWLINE + \
    "NANO,*AA:7.161800     AC:7.290000     AH:160.0000     AM:0" + NEWLINE + \
    "NANO,*AP:0            AR:160.0000     BL:0            BR1:115200" + NEWLINE + \
    "NANO,*BR2:115200      BV:10.9         BX:112          C1:-9747.897" + NEWLINE + \
    "NANO,*C2:288.5739     C3:27200.78     CF:BA0F         CM:4" + NEWLINE + \
    "NANO,*CS:7412         D1:.0572567     D2:.0000000     DH:2000.000" + NEWLINE + \
    "NANO,*DL:0            DM:0            DO:0            DP:6" + NEWLINE + \
    "NANO,*DZ:.0000000     EM:0            ET:0            FD:.153479" + NEWLINE + \
    "NANO,*FM:0            GD:0            GE:2            GF:0" + NEWLINE + \
    "NANO,*GP::            GT:1            IA1:8           IA2:12" + NEWLINE + \
    "NANO,*IB:0            ID:1            IE:0            IK:46" + NEWLINE + \
    "NANO,*IM:0            IS:5            IY:0            KH:0" + NEWLINE + \
    "NANO,*LH:2250.000     LL:.0000000     M1:13.880032    M3:14.090198" + NEWLINE + \
    "NANO,*MA:             MD:0            MU:             MX:0" + NEWLINE + \
    "NANO,*NO:0            OI:0            OP:2100.000     OR:1.00" + NEWLINE + \
    "NANO,*OY:1.000000     OZ:0            PA:.0000000     PC:.0000000" + NEWLINE + \
    "NANO,*PF:2000.000     PI:25           PL:2400.000     PM:1.000000" + NEWLINE + \
    "NANO,*PO:0            PR:238          PS:0            PT:N" + NEWLINE + \
    "NANO,*PX:3            RE:0            RS:5            RU:0" + NEWLINE + \
    "NANO,*SD:12           SE:0            SI:OFF          SK:0" + NEWLINE + \
    "NANO,*SL:0            SM:OFF          SP:0            ST:10" + NEWLINE + \
    "NANO,*SU:0            T1:30.00412     T2:1.251426     T3:50.64434" + NEWLINE + \
    "NANO,*T4:134.5816     T5:.0000000     TC:.6781681     TF:.00" + NEWLINE + \
    "NANO,*TH:1,P4;>OK     TI:25           TJ:2            TP:0" + NEWLINE + \
    "NANO,*TQ:1            TR:952          TS:1            TU:0" + NEWLINE + \
    "NANO,*U0:5.839037     UE:0            UF:1.000000" + NEWLINE + \
    "NANO,*UL:                             UM:user         UN:1" + NEWLINE + \
    "NANO,*US:0            VP:4            WI:Def=15:00-061311" + NEWLINE + \
    "NANO,*XC:8            XD:A            XM:1            XN:0" + NEWLINE + \
    "NANO,*XS:0011         XX:1            Y1:-3818.141    Y2:-10271.53" + NEWLINE + \
    "NANO,*Y3:.0000000     ZE:0            ZI:0            ZL:0" + NEWLINE + \
    "NANO,*ZM:0            ZS:0            ZV:.0000000" + NEWLINE


###############################################################################
#                           DRIVER TEST MIXIN                                  #
#     Defines a set of constants and assert methods used for data particle    #
#     verification                                                               #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.                                      #
###############################################################################
class NANOTestMixinSub(DriverTestMixin):
    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    STATES = ParameterTestConfigKey.STATES

    _driver_parameters = {
        # Parameters defined in the IOS
    }

    _sample_parameters_01 = {
        NANODataParticleKey.TIME: {TYPE: float, VALUE: 3586225716.0, REQUIRED: True},
        NANODataParticleKey.PRESSURE: {TYPE: float, VALUE: 13.888533, REQUIRED: True},
        NANODataParticleKey.TEMP: {TYPE: float, VALUE: 26.147947328, REQUIRED: True},
        NANODataParticleKey.PPS_SYNC: {TYPE: bool, VALUE: False, REQUIRED: True},
    }

    _sample_parameters_02 = {
        NANODataParticleKey.TIME: {TYPE: float, VALUE: 3586227216.0, REQUIRED: True},
        NANODataParticleKey.PRESSURE: {TYPE: float, VALUE: 13.884067, REQUIRED: True},
        NANODataParticleKey.TEMP: {TYPE: float, VALUE: 26.172926006, REQUIRED: True},
        NANODataParticleKey.PPS_SYNC: {TYPE: bool, VALUE: True, REQUIRED: True},
    }

    def assert_particle_sample_01(self, data_particle, verify_values=False):
        """
        Verify sample particle
        @param data_particle:  NANODataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(NANODataParticleKey, self._sample_parameters_01)
        self.assert_data_particle_header(data_particle, DataParticleType.NANO_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_01, verify_values)

    def assert_particle_sample_02(self, data_particle, verify_values=False):
        """
        Verify sample particle
        @param data_particle:  NANODataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(NANODataParticleKey, self._sample_parameters_02)
        self.assert_data_particle_header(data_particle, DataParticleType.NANO_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_02, verify_values)

    def assert_particle_sample_firehose(self, data_particle, verify_values=False):
        """
        Verify sample particle
        @param data_particle:  NANODataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(NANODataParticleKey, self._sample_parameters_01)
        self.assert_data_particle_header(data_particle, DataParticleType.NANO_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_01, verify_values)

    def assert_particle_status(self, status_particle, verify_values=False):
        pass


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
class DriverUnitTest(InstrumentDriverUnitTestCase, NANOTestMixinSub):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def _send_port_agent_packet(self, driver, data):
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(data)
        port_agent_packet.attach_timestamp(self.get_ntp_timestamp())
        port_agent_packet.pack_header()
        # Push the response into the driver
        driver._protocol.got_data(port_agent_packet)

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

        # Test capabilities for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)
        self.assert_chunker_sample(chunker, VALID_SAMPLE_01)
        self.assert_chunker_sample(chunker, DUMP_STATUS)

    def test_connect(self, initial_protocol_state=ProtocolState.COMMAND):
        """
        Test driver can change state to COMMAND
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, initial_protocol_state)
        return driver

    def test_data_build_parsed_values(self):
        """
        Verify that the BOTPT NANO driver build_parsed_values method
        raises SampleException when an invalid sample is encountered
        and that it returns a result when a valid sample is encountered
        """
        samples = [
            (INVALID_SAMPLE, False),
            (VALID_SAMPLE_01, True),
            (VALID_SAMPLE_02, True),
        ]

        for sample, is_valid in samples:
            sample_exception = False
            result = False
            try:
                test_particle = NANODataParticle(sample)
                result = test_particle._build_parsed_values()
            except SampleException as e:
                log.debug('SampleException caught: %s.', e)
                sample_exception = True
            finally:
                if is_valid:
                    self.assertTrue(isinstance(result, list))
                    self.assertFalse(sample_exception)
                else:
                    self.assertTrue(sample_exception)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        driver = self.test_connect()
        self.assert_particle_published(driver, VALID_SAMPLE_01, self.assert_particle_sample_01, True)
        self.assert_particle_published(driver, VALID_SAMPLE_02, self.assert_particle_sample_02, True)
        self.assert_particle_published(driver, BOTPT_FIREHOSE_01, self.assert_particle_sample_01, True)

    def test_status_01(self):
        """
        Verify that the driver correctly parses the DUMP-SETTINGS response
        """
        driver = self.test_connect()
        self._send_port_agent_packet(driver, DUMP_STATUS)

    def test_start_autosample(self):
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START_AUTOSAMPLE)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.AUTOSAMPLE)

    def test_stop_autosample(self):
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START_AUTOSAMPLE)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.AUTOSAMPLE)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.STOP_AUTOSAMPLE)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

        expected = [call(InstrumentCommand.DATA_ON + NEWLINE), call(InstrumentCommand.DATA_OFF + NEWLINE)]
        self.assertEqual(driver._connection.send.call_args_list, expected)

    def test_status_01_handler(self):
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.ACQUIRE_STATUS)
        driver._connection.send.assert_called_once_with(InstrumentCommand.DUMP_SETTINGS + NEWLINE)

    def test_dump_01(self):
        driver = self.test_connect()
        ts = self.get_ntp_timestamp()
        driver._protocol._got_chunk(DUMP_STATUS, ts)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
        protocol = Protocol(Prompt, NEWLINE, mock_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, NANOTestMixinSub):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_connection(self):
        self.assert_initialize_driver()

    def test_get(self):
        pass

    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        pass

    def test_data_on(self):
        """
        @brief Test for turning data on
        """
        self.assert_initialize_driver()

        # Set continuous data on
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)
        self.assert_state_change(ProtocolState.AUTOSAMPLE, 5)
        self.assert_async_particle_generation(DataParticleType.NANO_PARSED,
                                              self.assert_particle_sample_01, particle_count=10, timeout=15)
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
        self.assert_state_change(ProtocolState.COMMAND, 10)

    def test_dump_01(self):
        """
        @brief Test for acquiring status
        """
        self.assert_initialize_driver()
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_STATUS)
        self.assert_async_particle_generation(DataParticleType.NANO_STATUS, self.assert_particle_sample_01)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase, NANOTestMixinSub):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_poll(self):
        """
        No polling for a single sample
        """

    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        self.assert_enter_command_mode()

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
                ProtocolEvent.GET,
                ProtocolEvent.SET,
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.ACQUIRE_STATUS,
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [
            ProtocolEvent.STOP_AUTOSAMPLE,
            ProtocolEvent.ACQUIRE_STATUS,
        ]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()