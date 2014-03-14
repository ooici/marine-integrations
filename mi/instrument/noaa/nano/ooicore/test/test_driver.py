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

import unittest
import time

import ntplib
from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger;

log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType

from mi.core.instrument.port_agent_client import PortAgentClient
from mi.core.instrument.port_agent_client import PortAgentPacket

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from mi.instrument.noaa.nano.ooicore.driver import InstrumentDriver
from mi.instrument.noaa.nano.ooicore.driver import DataParticleType
from mi.instrument.noaa.nano.ooicore.driver import NANODataParticleKey
from mi.instrument.noaa.nano.ooicore.driver import NANODataParticle
from mi.instrument.noaa.nano.ooicore.driver import NANOCommandResponse
from mi.instrument.noaa.nano.ooicore.driver import NANOStatus01Particle
from mi.instrument.noaa.nano.ooicore.driver import InstrumentCommand
from mi.instrument.noaa.nano.ooicore.driver import ProtocolState
from mi.instrument.noaa.nano.ooicore.driver import ProtocolEvent
from mi.instrument.noaa.nano.ooicore.driver import Capability
from mi.instrument.noaa.nano.ooicore.driver import Parameter
from mi.instrument.noaa.nano.ooicore.driver import Protocol
from mi.instrument.noaa.nano.ooicore.driver import Prompt
from mi.instrument.noaa.nano.ooicore.driver import NEWLINE
from mi.instrument.noaa.nano.ooicore.driver import NANO_DATA_ON
from mi.instrument.noaa.nano.ooicore.driver import NANO_DUMP_SETTINGS

from mi.core.exceptions import SampleException
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent
from pyon.core.exception import Conflict

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.noaa.nano.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = '1D644T',
    instrument_agent_name = 'noaa_nano_ooicore',
    instrument_agent_packet_config = DataParticleType(),

    driver_startup_config = {}
)

GO_ACTIVE_TIMEOUT=180

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

INVALID_SAMPLE  = "This is an invalid sample; it had better cause an exception." + NEWLINE
VALID_SAMPLE_01 = "NANO,V,2013/08/22 22:48:36.013,13.888533,26.147947328" + NEWLINE
VALID_SAMPLE_02 = "NANO,V,2013/08/22 23:13:36.000,13.884067,26.172926006" + NEWLINE

BOTPT_FIREHOSE_01  = "NANO,V,2013/08/22 22:48:36.013,13.888533,26.147947328" + NEWLINE
BOTPT_FIREHOSE_01  += "LILY,2013/05/16 17:03:22,-202.490,-330.000,149.88, 25.72,11.88,N9656" + NEWLINE
BOTPT_FIREHOSE_01  += "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE
#BOTPT_FIREHOSE_01  += "NANO,2013/05/29 00:25:34, -0.0882, -0.7524,28.45,N8642" + NEWLINE
#BOTPT_FIREHOSE_01  += "NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840" + NEWLINE
BOTPT_FIREHOSE_01  += "LILY,2013/05/16 17:03:22,-202.490,-330.000,149.88, 25.72,11.88,N9656" + NEWLINE
BOTPT_FIREHOSE_01  += "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE

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
    "NANO,*C2:288.5739     C3:27200.78     CF:BA0F         CM:4" + NEWLINE +  \
    "NANO,*CS:7412         D1:.0572567     D2:.0000000     DH:2000.000" + NEWLINE +  \
    "NANO,*DL:0            DM:0            DO:0            DP:6" + NEWLINE +  \
    "NANO,*DZ:.0000000     EM:0            ET:0            FD:.153479" + NEWLINE +  \
    "NANO,*FM:0            GD:0            GE:2            GF:0" + NEWLINE +  \
    "NANO,*GP::            GT:1            IA1:8           IA2:12" + NEWLINE +  \
    "NANO,*IB:0            ID:1            IE:0            IK:46" + NEWLINE +  \
    "NANO,*IM:0            IS:5            IY:0            KH:0" + NEWLINE +  \
    "NANO,*LH:2250.000     LL:.0000000     M1:13.880032    M3:14.090198" + NEWLINE +  \
    "NANO,*MA:             MD:0            MU:             MX:0" + NEWLINE +  \
    "NANO,*NO:0            OI:0            OP:2100.000     OR:1.00" + NEWLINE +  \
    "NANO,*OY:1.000000     OZ:0            PA:.0000000     PC:.0000000" + NEWLINE +  \
    "NANO,*PF:2000.000     PI:25           PL:2400.000     PM:1.000000" + NEWLINE +  \
    "NANO,*PO:0            PR:238          PS:0            PT:N" + NEWLINE +  \
    "NANO,*PX:3            RE:0            RS:5            RU:0" + NEWLINE +  \
    "NANO,*SD:12           SE:0            SI:OFF          SK:0" + NEWLINE +  \
    "NANO,*SL:0            SM:OFF          SP:0            ST:10" + NEWLINE +  \
    "NANO,*SU:0            T1:30.00412     T2:1.251426     T3:50.64434" + NEWLINE +  \
    "NANO,*T4:134.5816     T5:.0000000     TC:.6781681     TF:.00" + NEWLINE +  \
    "NANO,*TH:1,P4;>OK     TI:25           TJ:2            TP:0" + NEWLINE +  \
    "NANO,*TQ:1            TR:952          TS:1            TU:0" + NEWLINE +  \
    "NANO,*U0:5.839037     UE:0            UF:1.000000" + NEWLINE +  \
    "NANO,*UL:                             UM:user         UN:1" + NEWLINE +  \
    "NANO,*US:0            VP:4            WI:Def=15:00-061311" + NEWLINE +  \
    "NANO,*XC:8            XD:A            XM:1            XN:0" + NEWLINE +  \
    "NANO,*XS:0011         XX:1            Y1:-3818.141    Y2:-10271.53" + NEWLINE +  \
    "NANO,*Y3:.0000000     ZE:0            ZI:0            ZL:0" + NEWLINE +  \
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


    TYPE      = ParameterTestConfigKey.TYPE
    READONLY  = ParameterTestConfigKey.READONLY
    STARTUP   = ParameterTestConfigKey.STARTUP
    DA        = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE     = ParameterTestConfigKey.VALUE
    REQUIRED  = ParameterTestConfigKey.REQUIRED
    DEFAULT   = ParameterTestConfigKey.DEFAULT
    STATES    = ParameterTestConfigKey.STATES

    _driver_parameters = {
        # Parameters defined in the IOS
    }
    
    _sample_parameters_01 = {
        NANODataParticleKey.TIME: {TYPE: float, VALUE: 3586227216.0, REQUIRED: True },
        NANODataParticleKey.PRESSURE: {TYPE: float, VALUE: 13.888533, REQUIRED: True },
        NANODataParticleKey.TEMP: {TYPE: float, VALUE: 26.147947328, REQUIRED: True },
    }

    _sample_parameters_02 = {
        NANODataParticleKey.TIME: {TYPE: float, VALUE: 3586227216.0, REQUIRED: True },
        NANODataParticleKey.PRESSURE: {TYPE: float, VALUE: 13.884067, REQUIRED: True },
        NANODataParticleKey.TEMP: {TYPE: float, VALUE: 26.172926006, REQUIRED: True },
    }

    def assert_particle_sample_01(self, data_particle, verify_values = False):
        '''
        Verify sample particle
        @param data_particle:  NANODataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(NANODataParticleKey, self._sample_parameters_01)
        self.assert_data_particle_header(data_particle, DataParticleType.NANO_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_01, verify_values)

    def assert_particle_sample_02(self, data_particle, verify_values = False):
        '''
        Verify sample particle
        @param data_particle:  NANODataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(NANODataParticleKey, self._sample_parameters_02)
        self.assert_data_particle_header(data_particle, DataParticleType.NANO_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_02, verify_values)

    def assert_particle_sample_firehose(self, data_particle, verify_values = False):
        '''
        Verify sample particle
        @param data_particle:  NANODataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(NANODataParticleKey, self._sample_parameters_01)
        self.assert_data_particle_header(data_particle, DataParticleType.NANO_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_01, verify_values)

    def assert_particle_status(self, status_particle, verify_values = False):
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
@attr('UNIT', group='mi')
class DriverUnitTest(InstrumentDriverUnitTestCase, NANOTestMixinSub):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(InstrumentCommand())

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())


    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, VALID_SAMPLE_01)
        self.assert_chunker_sample(chunker, DUMP_STATUS)
        self.assert_chunker_sample(chunker, DUMP_STATUS)


    """
    Test the connection to the BOTPT
    """
    def test_connect(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """

        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=PortAgentClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)

        """
        Now configure the driver with the mock_port_agent, verifying
        that the driver transitions to the DISCONNECTED state
        """
        config = {'mock_port_agent' : mock_port_agent}
        driver.configure(config = config)
        #self.assert_initialize_driver(driver)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)

        # Invoke the connect method of the driver: should connect to mock
        # port agent.  Verify that the connection FSM UNKNOWN.
        driver.connect()
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

    """
    Verify that the BOTPT NANO driver build_parsed_values method
    raises SampleException when an invalid sample is encountered
    and that it returns a result when a valid sample is encountered
    """
    def test_data_build_parsed_values(self):
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        sampleException = False
        try:        
            #driver._protocol._raw_data = "test that SampleException works"
            raw_data = INVALID_SAMPLE
            test_particle = NANODataParticle(raw_data)
            test_particle._build_parsed_values()
            
        except SampleException as e:
            log.debug('SampleException caught: %s.', e)
            sampleException = True
            
        finally:
            self.assertTrue(sampleException)

        sampleException = False
        result = None
        try:
            raw_data = VALID_SAMPLE_01
            test_particle = NANODataParticle(raw_data)
            result = test_particle._build_parsed_values()

        except SampleException as e:
            log.error('SampleException caught: %s.', e)
            sampleException = True
            
        finally:
            """
            Assert that the sampleException was not called.  Also assert that
            the result is a list.  Not getting into the details of the result
            here; that's done elsewhere.
            """
            self.assertFalse(sampleException)
            self.assertTrue(isinstance(result, list))

    """
    Verify that check_data_on_off_response raises a SampleException given an
    invalid response, and that it returns True given a valid response
    """
    def test_check_command_response(self):
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        sampleException = False
        try:
            response = NANOCommandResponse(INVALID_SAMPLE)
            retValue = response.check_command_response(NANO_DATA_ON)
        
        except SampleException as e:
            log.debug('SampleException caught: %s.', e)
            sampleException = True
            
        finally:
            self.assertTrue(sampleException)

    """
    Verify that set_time response is handled
    """
    def test_set_time_response(self):
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        sampleException = False
        try:
            response = NANOCommandResponse(SET_TIME_RESPONSE)
            retValue = response.check_command_response(NANO_DATA_ON)
        
        except SampleException as e:
            log.debug('SampleException caught: %s.', e)
            sampleException = True
            
        finally:
            #self.assertTrue(sampleException)
            self.assertTrue(retValue)

    def test_get_response_set_time_response(self):
        mock_port_agent = Mock(spec=PortAgentClient)
        driver = InstrumentDriver(self._got_data_event_callback)

        # Put the driver into test mode
        driver.set_test_mode(True)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)

        # Now configure the driver with the mock_port_agent, verifying
        # that the driver transitions to that state
        config = {'mock_port_agent' : mock_port_agent}
        driver.configure(config = config)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)

        # Invoke the connect method of the driver: should connect to mock
        # port agent.  Verify that the connection FSM transitions to CONNECTED,
        # (which means that the FSM should now be reporting the ProtocolState).
        driver.connect()
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        ts = ntplib.system_to_ntp_time(time.time())

        # DHE: need to return the status as a string; so, right now we check
        # the command response to the dump commands (which is totally bogus 
        # because it just echos exactly what we send, even if it's wrong)
        # but we really want to return the status as a string.  Might have to
        # expose the two commands to run separately instead of one combined
        # acquire_status
        driver._protocol._got_chunk(SET_TIME_RESPONSE, ts)

        response = driver._protocol._get_response(timeout = 0, expected_prompt = 'Test')

        # Force the instrument into command mode
        self.assert_force_state(driver, DriverProtocolState.AUTOSAMPLE)

        ts = ntplib.system_to_ntp_time(time.time())

        driver._protocol._got_chunk(SET_TIME_RESPONSE, ts)

        response = driver._protocol._get_response(timeout = 0, expected_prompt = 'Test')

    def test_handler_set_time_response(self):
        mock_port_agent = Mock(spec=PortAgentClient)
        driver = InstrumentDriver(self._got_data_event_callback)
        
        # Put the driver into test mode
        driver.set_test_mode(True)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)

        # Now configure the driver with the mock_port_agent, verifying
        # that the driver transitions to that state
        config = {'mock_port_agent' : mock_port_agent}
        driver.configure(config = config)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)

        # Invoke the connect method of the driver: should connect to mock
        # port agent.  Verify that the connection FSM transitions to CONNECTED,
        # (which means that the FSM should now be reporting the ProtocolState).
        driver.connect()
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        # Force the instrument into a known state
        self.assert_force_state(driver, DriverProtocolState.COMMAND)

        result = driver._protocol._handler_command_autosample_set_time(timeout = 0)
        #result = driver._protocol._handler_command_autosample_set_time(timeout = 0)
        ts = ntplib.system_to_ntp_time(time.time())


    """
    Verify that the BOTPT NANO driver publishes its particles correctly
    """
    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_particle_published(driver, VALID_SAMPLE_01, self.assert_particle_sample_01, True)
        self.assert_particle_published(driver, VALID_SAMPLE_02, self.assert_particle_sample_02, True)

    """
    Verify that the BOTPT NANO driver publishes a particle correctly when the NANO packet is 
    embedded in the stream of other BOTPT sensor output.
    """
    def test_firehose(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_particle_published(driver, BOTPT_FIREHOSE_01, self.assert_particle_sample_01, True)


    """
    Verify that the driver correctly parses the DUMP-SETTINGS response
    """
    def test_status_01(self):
        """
        """
        mock_port_agent = Mock(spec=PortAgentClient)
        driver = InstrumentDriver(self._got_data_event_callback)
        driver.set_test_mode(True)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)

        # Now configure the driver with the mock_port_agent, verifying
        # that the driver transitions to that state
        config = {'mock_port_agent' : mock_port_agent}
        driver.configure(config = config)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)

        # Invoke the connect method of the driver: should connect to mock
        # port agent.  Verify that the connection FSM transitions to CONNECTED,
        # (which means that the FSM should now be reporting the ProtocolState).
        driver.connect()
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        # Force the instrument into a known state
        self.assert_force_state(driver, DriverProtocolState.COMMAND)
        ts = ntplib.system_to_ntp_time(time.time())

        log.debug("DUMP_STATUS: %s", DUMP_STATUS)
        # Create and populate the port agent packet.
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(DUMP_STATUS)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("HEAT,2013/06/19 23:04:37,-001,0000,0026" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("LILY,2013/06/19 23:04:38, -49.455,  34.009,193.91, 26.02,11.96,N9655" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,V,2013/06/19 23:04:38.000,13.987223,25.126694121" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("LILY,2013/06/19 23:04:39, -49.483,  33.959,193.85, 26.03,11.96,N9655" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,V,2013/06/19 23:04:39.000,13.987191,25.126709409" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("LILY,2013/06/19 23:04:40, -49.355,  33.956,193.79, 26.02,11.96,N9655" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,V,2013/06/19 23:04:40.000,13.987253,25.126725854" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("HEAT,2013/06/19 23:04:40,-001,0000,0026" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:54,*APPLIED GEOMECHANICS Model MD900-T Firmware V5.2 SN-N3616 ID01" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,V,2013/06/19 21:46:54.000,13.990480,25.027793612" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        #driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:54,*01: Vbias= 0.0000 0.0000 0.0000 0.0000" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:54,*01: Vgain= 0.0000 0.0000 0.0000 0.0000" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:54,*01: Vmin:  -2.50  -2.50   2.50   2.50" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:54,*01: Vmax:   2.50   2.50   2.50   2.50" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:54,*01: a0=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:54,*01: a1=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:54,*01: a2=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:54,*01: a3=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:55,*01: Tcoef 0: Ks=           0 Kz=           0 Tcal=           0" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:55,*01: Tcoef 1: Ks=           0 Kz=           0 Tcal=           0" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:55,*01: N_SAMP= 460 Xzero=  0.00 Yzero=  0.00" + NEWLINE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 21:46:55,*01: TR-PASH-OFF E99-ON  SO-NMEA-SIM XY-EP  9600 baud FV-   " + NEWLINE)   
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)

        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data("NANO,2013/06/19 22:04:55,*9900XY-DUMP-SETTINGS" + NEWLINE)   
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()
        driver._protocol.got_data(port_agent_packet)


    """
    Verify that the driver correctly parses the DUMP_SETTINGS response
    """
    @unittest.skip("NANO doesn't send responses to commands")
    def test_dump_settings_response(self):
        """
        """
        mock_port_agent = Mock(spec=PortAgentClient)
        driver = InstrumentDriver(self._got_data_event_callback)
        driver.set_test_mode(True)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)

        # Now configure the driver with the mock_port_agent, verifying
        # that the driver transitions to that state
        config = {'mock_port_agent' : mock_port_agent}
        driver.configure(config = config)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)

        # Invoke the connect method of the driver: should connect to mock
        # port agent.  Verify that the connection FSM transitions to CONNECTED,
        # (which means that the FSM should now be reporting the ProtocolState).
        driver.connect()
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        # Force the instrument into a known state
        self.assert_force_state(driver, DriverProtocolState.COMMAND)
        ts = ntplib.system_to_ntp_time(time.time())

        log.debug("DUMP_SETTINGS command response: %s", DUMP_COMMAND_RESPONSE)
        # Create and populate the port agent packet.
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(DUMP_COMMAND_RESPONSE)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()

        # Push the response into the driver
        driver._protocol.got_data(port_agent_packet)
        response = driver._protocol._get_response(expected_prompt = 
                                                       NANO_DUMP_SETTINGS)
        
        self.assertTrue(isinstance(response[1], NANOCommandResponse))


    def test_start_autosample(self):
        mock_port_agent = Mock(spec=PortAgentClient)
        driver = InstrumentDriver(self._got_data_event_callback)
        
        # Put the driver into test mode
        driver.set_test_mode(True)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)

        # Now configure the driver with the mock_port_agent, verifying
        # that the driver transitions to that state
        config = {'mock_port_agent' : mock_port_agent}
        driver.configure(config = config)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)

        # Invoke the connect method of the driver: should connect to mock
        # port agent.  Verify that the connection FSM transitions to CONNECTED,
        # (which means that the FSM should now be reporting the ProtocolState).
        driver.connect()
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        # Force the instrument into a known state
        self.assert_force_state(driver, DriverProtocolState.COMMAND)

        result = driver._protocol._handler_command_start_autosample(timeout = 0)
        ts = ntplib.system_to_ntp_time(time.time())

    def test_stop_autosample(self):
        mock_port_agent = Mock(spec=PortAgentClient)
        driver = InstrumentDriver(self._got_data_event_callback)

        # Put the driver into test mode
        driver.set_test_mode(True)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)

        # Now configure the driver with the mock_port_agent, verifying
        # that the driver transitions to that state
        config = {'mock_port_agent' : mock_port_agent}
        driver.configure(config = config)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)

        # Invoke the connect method of the driver: should connect to mock
        # port agent.  Verify that the connection FSM transitions to CONNECTED,
        # (which means that the FSM should now be reporting the ProtocolState).
        driver.connect()
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        # Force the instrument into a known state
        self.assert_force_state(driver, DriverProtocolState.AUTOSAMPLE)

        result = driver._protocol._handler_autosample_stop_autosample()
        ts = ntplib.system_to_ntp_time(time.time())


    def test_status_01_handler(self):
        mock_port_agent = Mock(spec=PortAgentClient)
        driver = InstrumentDriver(self._got_data_event_callback)

        def my_send(data):
            my_response = DUMP_STATUS
            log.debug("my_send: data: %s, my_response: %s", data, my_response)
            driver._protocol._promptbuf += my_response
            return len(DUMP_STATUS)
        mock_port_agent.send.side_effect = my_send
        
        # Put the driver into test mode
        driver.set_test_mode(True)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)

        # Now configure the driver with the mock_port_agent, verifying
        # that the driver transitions to that state
        config = {'mock_port_agent' : mock_port_agent}
        driver.configure(config = config)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)

        # Invoke the connect method of the driver: should connect to mock
        # port agent.  Verify that the connection FSM transitions to CONNECTED,
        # (which means that the FSM should now be reporting the ProtocolState).
        driver.connect()
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        # Force the instrument into a known state
        self.assert_force_state(driver, DriverProtocolState.AUTOSAMPLE)

        result = driver._protocol._handler_command_autosample_dump01(timeout = 0)

    def test_dump_01(self):
        mock_port_agent = Mock(spec=PortAgentClient)
        driver = InstrumentDriver(self._got_data_event_callback)

        # Put the driver into test mode
        driver.set_test_mode(True)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)

        # Now configure the driver with the mock_port_agent, verifying
        # that the driver transitions to that state
        config = {'mock_port_agent' : mock_port_agent}
        driver.configure(config = config)

        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)

        # Invoke the connect method of the driver: should connect to mock
        # port agent.  Verify that the connection FSM transitions to CONNECTED,
        # (which means that the FSM should now be reporting the ProtocolState).
        driver.connect()
        current_state = driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        # Force the instrument into command mode
        self.assert_force_state(driver, DriverProtocolState.COMMAND)

        ts = ntplib.system_to_ntp_time(time.time())

        # DHE: need to return the status as a string; so, right now we check
        # the command response to the dump commands (which is totally bogus 
        # because it just echos exactly what we send, even if it's wrong)
        # but we really want to return the status as a string.  Might have to
        # expose the two commands to run separately instead of one combined
        # acquire_status
        driver._protocol._got_chunk(DUMP_STATUS, ts)

        response = driver._protocol._get_response(timeout = 0, expected_prompt = 'Test')
        self.assertTrue(isinstance(response[1], NANOStatus01Particle))


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
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_connection(self):
        self.assert_initialize_driver()

    def test_get(self):
        #self.assert_initialize_driver()
        #value = self.assert_get(Parameter.HEAT_DURATION)
        pass

    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        #self.assert_initialize_driver()

        #self.assert_set(Parameter.HEAT_DURATION, TEST_HEAT_ON_DURATION_2)
        #value = self.assert_get(Parameter.HEAT_DURATION, TEST_HEAT_ON_DURATION_2)
        pass

    def test_data_on(self):
        """
        @brief Test for turning data on
        """
        self.assert_initialize_driver()

        """
        Set continuous data on 
        """
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)
        #self.assertEqual(response[1], NANO_DATA_ON)
        
        #log.debug("DATA_ON returned: %r", response)

        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
        #self.assertEqual(response[1], NANO_DATA_OFF)
        
        #log.debug("DATA_OFF returned: %r", response)

    def test_dump_01(self):
        """
        @brief Test for acquiring status
        """
        self.assert_initialize_driver()

        """
        Issues acquire status command 
        """
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.DUMP_SETTINGS)
        log.debug("DUMP_SETTINGS returned: %r", response)
        

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

    def test_reset(self):
        """
        Verify the agent can be reset
        """
        self.assert_enter_command_mode()
        self.assert_reset()

        self.assert_enter_command_mode()
        self.assert_start_autosample()
        self.assert_reset()

    # Overridden because does not apply for this driver
    def test_discover(self):
        pass
            
    def test_poll(self):
        '''
        No polling for a single sample
        '''

    def test_get_set_parameters(self):
        '''
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        '''
        self.assert_enter_command_mode()


    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
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
                ProtocolEvent.DUMP_SETTINGS,
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
                ProtocolEvent.DUMP_SETTINGS,
            ]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()



    def test_instrument_agent_common_state_model_lifecycle(self,  timeout=GO_ACTIVE_TIMEOUT):
        """
        @brief Test agent state transitions.
               This test verifies that the instrument agent can
               properly command the instrument through the following states.

                COMMANDS TESTED
                *ResourceAgentEvent.INITIALIZE
                *ResourceAgentEvent.RESET
                *ResourceAgentEvent.GO_ACTIVE
                *ResourceAgentEvent.RUN
                *ResourceAgentEvent.PAUSE
                *ResourceAgentEvent.RESUME
                *ResourceAgentEvent.GO_COMMAND
                *ResourceAgentEvent.GO_INACTIVE
                *ResourceAgentEvent.PING_RESOURCE
                *ResourceAgentEvent.CLEAR

                COMMANDS NOT TESTED
                * ResourceAgentEvent.GO_DIRECT_ACCESS
                * ResourceAgentEvent.GET_RESOURCE_STATE
                * ResourceAgentEvent.GET_RESOURCE
                * ResourceAgentEvent.SET_RESOURCE
                * ResourceAgentEvent.EXECUTE_RESOURCE

                STATES ACHIEVED:
                * ResourceAgentState.UNINITIALIZED
                * ResourceAgentState.INACTIVE
                * ResourceAgentState.IDLE'
                * ResourceAgentState.STOPPED
                * ResourceAgentState.COMMAND

                STATES NOT ACHIEVED:
                * ResourceAgentState.DIRECT_ACCESS
                * ResourceAgentState.STREAMING
                * ResourceAgentState.TEST
                * ResourceAgentState.CALIBRATE
                * ResourceAgentState.BUSY
                -- Not tested because they may not be implemented in the driver
        """
        ####
        # UNINITIALIZED
        ####
        self.assert_agent_state(ResourceAgentState.UNINITIALIZED)

        # Try to run some commands that aren't available in this state
        self.assert_agent_command_exception(ResourceAgentEvent.RUN, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_ACTIVE, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_DIRECT_ACCESS, exception_class=Conflict)

        ####
        # INACTIVE
        ####
        self.assert_agent_command(ResourceAgentEvent.INITIALIZE)
        self.assert_agent_state(ResourceAgentState.INACTIVE)

        # Try to run some commands that aren't available in this state
        self.assert_agent_command_exception(ResourceAgentEvent.RUN, exception_class=Conflict)

        ####
        # IDLE
        ####
        self.assert_agent_command(ResourceAgentEvent.GO_ACTIVE, timeout=600)

        # Try to run some commands that aren't available in this state
        self.assert_agent_command_exception(ResourceAgentEvent.INITIALIZE, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_ACTIVE, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.RESUME, exception_class=Conflict)

        # Verify we can go inactive
        self.assert_agent_command(ResourceAgentEvent.GO_INACTIVE)
        self.assert_agent_state(ResourceAgentState.INACTIVE)

        # Get back to idle
        self.assert_agent_command(ResourceAgentEvent.GO_ACTIVE, timeout=600)

        # Reset
        self.assert_agent_command(ResourceAgentEvent.RESET)
        self.assert_agent_state(ResourceAgentState.UNINITIALIZED)

