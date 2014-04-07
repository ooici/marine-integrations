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
import time

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr
from mock import Mock

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

from mi.instrument.noaa.botpt.nano.driver import InstrumentDriver, NANOStatusParticleKey, NANO_STRING
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
    "NANO,*______________________________________________________________" + NEWLINE + \
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
    "NANO,*ZM:0            ZS:0            ZV:.0000000"


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

    _status_parameters = {
        NANOStatusParticleKey.MODEL_NUMBER: {TYPE: unicode, VALUE: u'42.4K-265', REQUIRED: True},
        NANOStatusParticleKey.SERIAL_NUMBER: {TYPE: unicode, VALUE: u'120785', REQUIRED: True},
        NANOStatusParticleKey.FIRMWARE_REVISION: {TYPE: unicode, VALUE: u'R5.20', REQUIRED: True},
        NANOStatusParticleKey.FIRMWARE_DATE: {TYPE: unicode, VALUE: u'03-25-13', REQUIRED: True},
        NANOStatusParticleKey.PPS_STATUS: {TYPE: unicode, VALUE: u'V : PPS signal NOT detected.', REQUIRED: True},
        NANOStatusParticleKey.AA: {TYPE: float, VALUE: 7.1618, REQUIRED: True},
        NANOStatusParticleKey.AC: {TYPE: float, VALUE: 7.29, REQUIRED: True},
        NANOStatusParticleKey.AH: {TYPE: float, VALUE: 160.0, REQUIRED: True},
        NANOStatusParticleKey.AM: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.AP: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.AR: {TYPE: float, VALUE: 160.0, REQUIRED: True},
        NANOStatusParticleKey.BL: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.BR1: {TYPE: int, VALUE: 115200, REQUIRED: True},
        NANOStatusParticleKey.BR2: {TYPE: int, VALUE: 115200, REQUIRED: True},
        NANOStatusParticleKey.BV: {TYPE: float, VALUE: 10.9, REQUIRED: True},
        NANOStatusParticleKey.BX: {TYPE: int, VALUE: 112, REQUIRED: True},
        NANOStatusParticleKey.C1: {TYPE: float, VALUE: -9747.897, REQUIRED: True},
        NANOStatusParticleKey.C2: {TYPE: float, VALUE: 288.5739, REQUIRED: True},
        NANOStatusParticleKey.C3: {TYPE: float, VALUE: 27200.78, REQUIRED: True},
        NANOStatusParticleKey.CF: {TYPE: unicode, VALUE: u'BA0F', REQUIRED: True},
        NANOStatusParticleKey.CM: {TYPE: int, VALUE: 4, REQUIRED: True},
        NANOStatusParticleKey.CS: {TYPE: int, VALUE: 7412, REQUIRED: True},
        NANOStatusParticleKey.D1: {TYPE: float, VALUE: 0.0572567, REQUIRED: True},
        NANOStatusParticleKey.D2: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        NANOStatusParticleKey.DH: {TYPE: float, VALUE: 2000.0, REQUIRED: True},
        NANOStatusParticleKey.DL: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.DM: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.DO: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.DP: {TYPE: int, VALUE: 6, REQUIRED: True},
        NANOStatusParticleKey.DZ: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        NANOStatusParticleKey.EM: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.ET: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.FD: {TYPE: float, VALUE: 0.153479, REQUIRED: True},
        NANOStatusParticleKey.FM: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.GD: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.GE: {TYPE: int, VALUE: 2, REQUIRED: True},
        NANOStatusParticleKey.GF: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.GP: {TYPE: unicode, VALUE: u':', REQUIRED: True},
        NANOStatusParticleKey.GT: {TYPE: int, VALUE: 1, REQUIRED: True},
        NANOStatusParticleKey.IA1: {TYPE: int, VALUE: 8, REQUIRED: True},
        NANOStatusParticleKey.IA2: {TYPE: int, VALUE: 12, REQUIRED: True},
        NANOStatusParticleKey.IB: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.ID: {TYPE: int, VALUE: 1, REQUIRED: True},
        NANOStatusParticleKey.IE: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.IK: {TYPE: int, VALUE: 46, REQUIRED: True},
        NANOStatusParticleKey.IM: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.IS: {TYPE: int, VALUE: 5, REQUIRED: True},
        NANOStatusParticleKey.IY: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.KH: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.LH: {TYPE: float, VALUE: 2250.0, REQUIRED: True},
        NANOStatusParticleKey.LL: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        NANOStatusParticleKey.M1: {TYPE: float, VALUE: 13.880032, REQUIRED: True},
        NANOStatusParticleKey.M3: {TYPE: float, VALUE: 14.090198, REQUIRED: True},
        NANOStatusParticleKey.MA: {TYPE: unicode, VALUE: u'', REQUIRED: True},
        NANOStatusParticleKey.MD: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.MU: {TYPE: unicode, VALUE: u'', REQUIRED: True},
        NANOStatusParticleKey.MX: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.NO: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.OI: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.OP: {TYPE: float, VALUE: 2100.0, REQUIRED: True},
        NANOStatusParticleKey.OR: {TYPE: float, VALUE: 1.0, REQUIRED: True},
        NANOStatusParticleKey.OY: {TYPE: float, VALUE: 1.0, REQUIRED: True},
        NANOStatusParticleKey.OZ: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.PA: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        NANOStatusParticleKey.PC: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        NANOStatusParticleKey.PF: {TYPE: float, VALUE: 2000.0, REQUIRED: True},
        NANOStatusParticleKey.PI: {TYPE: int, VALUE: 25, REQUIRED: True},
        NANOStatusParticleKey.PL: {TYPE: float, VALUE: 2400.0, REQUIRED: True},
        NANOStatusParticleKey.PM: {TYPE: float, VALUE: 1.0, REQUIRED: True},
        NANOStatusParticleKey.PO: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.PR: {TYPE: int, VALUE: 238, REQUIRED: True},
        NANOStatusParticleKey.PS: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.PT: {TYPE: unicode, VALUE: u'N', REQUIRED: True},
        NANOStatusParticleKey.PX: {TYPE: int, VALUE: 3, REQUIRED: True},
        NANOStatusParticleKey.RE: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.RS: {TYPE: int, VALUE: 5, REQUIRED: True},
        NANOStatusParticleKey.RU: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.SD: {TYPE: int, VALUE: 12, REQUIRED: True},
        NANOStatusParticleKey.SE: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.SI: {TYPE: unicode, VALUE: u'OFF', REQUIRED: True},
        NANOStatusParticleKey.SK: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.SL: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.SM: {TYPE: unicode, VALUE: u'OFF', REQUIRED: True},
        NANOStatusParticleKey.SP: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.ST: {TYPE: int, VALUE: 10, REQUIRED: True},
        NANOStatusParticleKey.SU: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.T1: {TYPE: float, VALUE: 30.00412, REQUIRED: True},
        NANOStatusParticleKey.T2: {TYPE: float, VALUE: 1.251426, REQUIRED: True},
        NANOStatusParticleKey.T3: {TYPE: float, VALUE: 50.64434, REQUIRED: True},
        NANOStatusParticleKey.T4: {TYPE: float, VALUE: 134.5816, REQUIRED: True},
        NANOStatusParticleKey.T5: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        NANOStatusParticleKey.TC: {TYPE: float, VALUE: 0.6781681, REQUIRED: True},
        NANOStatusParticleKey.TF: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        NANOStatusParticleKey.TH: {TYPE: unicode, VALUE: u'1,P4;>OK', REQUIRED: True},
        NANOStatusParticleKey.TI: {TYPE: int, VALUE: 25, REQUIRED: True},
        NANOStatusParticleKey.TJ: {TYPE: int, VALUE: 2, REQUIRED: True},
        NANOStatusParticleKey.TP: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.TQ: {TYPE: int, VALUE: 1, REQUIRED: True},
        NANOStatusParticleKey.TR: {TYPE: int, VALUE: 952, REQUIRED: True},
        NANOStatusParticleKey.TS: {TYPE: int, VALUE: 1, REQUIRED: True},
        NANOStatusParticleKey.TU: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.U0: {TYPE: float, VALUE: 5.839037, REQUIRED: True},
        NANOStatusParticleKey.UE: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.UF: {TYPE: float, VALUE: 1.0, REQUIRED: True},
        NANOStatusParticleKey.UL: {TYPE: unicode, VALUE: u'', REQUIRED: True},
        NANOStatusParticleKey.UM: {TYPE: unicode, VALUE: u'user', REQUIRED: True},
        NANOStatusParticleKey.UN: {TYPE: int, VALUE: 1, REQUIRED: True},
        NANOStatusParticleKey.US: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.VP: {TYPE: int, VALUE: 4, REQUIRED: True},
        NANOStatusParticleKey.WI: {TYPE: unicode, VALUE: u'Def=15:00-061311', REQUIRED: True},
        NANOStatusParticleKey.XC: {TYPE: int, VALUE: 8, REQUIRED: True},
        NANOStatusParticleKey.XD: {TYPE: unicode, VALUE: u'A', REQUIRED: True},
        NANOStatusParticleKey.XM: {TYPE: int, VALUE: 1, REQUIRED: True},
        NANOStatusParticleKey.XN: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.XS: {TYPE: int, VALUE: 11, REQUIRED: True},
        NANOStatusParticleKey.XX: {TYPE: int, VALUE: 1, REQUIRED: True},
        NANOStatusParticleKey.Y1: {TYPE: float, VALUE: -3818.141, REQUIRED: True},
        NANOStatusParticleKey.Y2: {TYPE: float, VALUE: -10271.53, REQUIRED: True},
        NANOStatusParticleKey.Y3: {TYPE: float, VALUE: 0.0, REQUIRED: True},
        NANOStatusParticleKey.ZE: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.ZI: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.ZL: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.ZM: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.ZS: {TYPE: int, VALUE: 0, REQUIRED: True},
        NANOStatusParticleKey.ZV: {TYPE: float, VALUE: 0.0, REQUIRED: True},
    }

    def assert_particle(self, data_particle, particle_key, particle_type, params, verify_values=False):
        """
        Verify sample particle
        """
        self.assert_data_particle_keys(particle_key, params)
        self.assert_data_particle_header(data_particle, particle_type, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, params, verify_values)

    def assert_particle_sample_01(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, NANODataParticleKey, DataParticleType.NANO_PARSED,
                             self._sample_parameters_01, verify_values)

    def assert_particle_sample_02(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, NANODataParticleKey, DataParticleType.NANO_PARSED,
                             self._sample_parameters_02, verify_values)

    def assert_particle_status(self, data_particle, verify_values=False):
        self.assert_particle(data_particle, NANOStatusParticleKey, DataParticleType.NANO_STATUS,
                             self._status_parameters, verify_values)


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

    @staticmethod
    def my_send(driver):
        def inner(data):
            if data.startswith(InstrumentCommand.DATA_ON):
                my_response = NANO_STRING + NEWLINE
            elif data.startswith(InstrumentCommand.DUMP_SETTINGS):
                my_response = DUMP_STATUS + NEWLINE
            else:
                my_response = None
            if my_response is not None:
                log.debug("my_send: data: %s, my_response: %s", data, my_response)
                driver._protocol._promptbuf += my_response
                driver._protocol._linebuf += my_response
                return len(my_response)

        return inner

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
        driver._connection.send.side_effect = self.my_send(driver)
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

    def test_status(self):
        """
        Verify that the driver correctly parses the DUMP-SETTINGS response
        """
        driver = self.test_connect()
        self._send_port_agent_packet(driver, DUMP_STATUS)

    def test_start_autosample(self):
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.START_AUTOSAMPLE)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.AUTOSAMPLE)
        driver._connection.send.assert_called_once_with(InstrumentCommand.DATA_ON + NEWLINE)

    def test_stop_autosample(self):
        driver = self.test_connect(initial_protocol_state=ProtocolState.AUTOSAMPLE)
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.STOP_AUTOSAMPLE)
        self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)
        driver._connection.send.assert_called_once_with(InstrumentCommand.DATA_OFF + NEWLINE)

    def test_status_01_handler(self):
        driver = self.test_connect()
        driver._protocol._protocol_fsm.on_event(ProtocolEvent.ACQUIRE_STATUS)
        driver._connection.send.assert_called_once_with(InstrumentCommand.DUMP_SETTINGS + NEWLINE)

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

    def assert_particle_count(self, particle_type, particle_count, timeout):
        end_time = time.time() + timeout
        while True:
            num_samples = len(self.get_sample_events(particle_type))
            if num_samples > particle_count:
                elapsed = timeout - (end_time - time.time())
                rate = 1.0 * num_samples / elapsed
                log.debug('Found %d samples, approx data rate: %.2f Hz', num_samples, rate)
                break
            else:
                log.debug('Found %d samples of %d expected', num_samples, particle_count)
            self.assertGreater(end_time, time.time(), msg="Timeout waiting for sample")
            time.sleep(.1)

    def test_connection(self):
        self.assert_initialize_driver()

    def test_commands(self):
        self.assert_initialize_driver()
        self.assert_driver_command(ProtocolEvent.SET_TIME)
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS)

    def test_get(self):
        self.assert_initialize_driver()
        self.assert_get(Parameter.OUTPUT_RATE, 40)

    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()
        test_data = [
            (Parameter.OUTPUT_RATE, 1, True),
            (Parameter.OUTPUT_RATE, 40, True),
            (Parameter.OUTPUT_RATE, -1, False),
            (Parameter.SYNC_INTERVAL, 1, True),
            (Parameter.SYNC_INTERVAL, 'x', False),
        ]

        for param, value, is_valid in test_data:
            threw_exception = False
            try:
                self.assert_set(param, value)
            except:
                threw_exception = True
            self.assertNotEqual(is_valid, threw_exception)

    def test_data_rates(self):
        self.assert_initialize_driver()
        self.assert_set(Parameter.OUTPUT_RATE, 1)
        self.assert_particle_generation(ProtocolEvent.START_AUTOSAMPLE, DataParticleType.NANO_PARSED,
                                        self.assert_particle_sample_01, delay=5)
        try:
            self.assert_particle_count(DataParticleType.NANO_PARSED, particle_count=20, timeout=5)
            self.assertTrue(False, msg='Generated too many particles for 1 Hz!')
        except AssertionError:
            pass
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
        self.assert_state_change(ProtocolState.COMMAND, 5)
        self.assert_set(Parameter.OUTPUT_RATE, 40)
        # testing each particle takes too long, making it difficult to verify that we are actually
        # sampling at 40Hz.  Instead we will just get a count.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)
        # Wait up to 12 seconds to get 400 samples
        self.assert_particle_count(DataParticleType.NANO_PARSED, particle_count=400, timeout=12)

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

    def test_acquire_status(self):
        """
        @brief Test for acquiring status
        """
        self.assert_initialize_driver()
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.NANO_STATUS,
                                        self.assert_particle_status, delay=2)


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